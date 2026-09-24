"""Prompts pre-generated at startup, served when live generation fails."""

import json
import logging
import random
import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel

from app import llm
from app.db import connect

logger = logging.getLogger(__name__)

# The free tier limits requests per day, so warm-up asks for every prompt in one request and makes
# at most one more if fewer than half came back usable.
MAX_WARM_UP_REQUESTS = 2


class StoredPrompt(BaseModel):
    subject: str
    prompt: str
    example: str


def load_subjects(path: Path) -> list[str]:
    try:
        subjects = json.loads(path.read_text())
    except FileNotFoundError:
        logger.warning("Subjects file %s not found; skipping prompt warm-up", path)
        return []
    return [s.strip() for s in subjects if isinstance(s, str) and s.strip()]


def save(db: sqlite3.Connection, prompt: StoredPrompt) -> None:
    db.execute(
        "INSERT INTO stored_prompts (subject, prompt, example) VALUES (?, ?, ?)",
        (prompt.subject, prompt.prompt, prompt.example),
    )
    db.commit()


def count(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM stored_prompts").fetchone()[0]


def find_fallback(db: sqlite3.Connection, subject: str) -> StoredPrompt | None:
    """A stored prompt for `subject` if there is one, otherwise any stored prompt."""
    row = db.execute(
        "SELECT subject, prompt, example FROM stored_prompts ORDER BY (subject = ?) DESC, RANDOM() LIMIT 1",
        (subject,),
    ).fetchone()
    return StoredPrompt(**row) if row else None


class PromptWarmer:
    """Pre-generates `target` prompts (one per distinct subject) on a background thread."""

    def __init__(
        self,
        db_path: Path,
        subjects: list[str],
        target: int,
        generate_batch: Callable[[list[str]], list[StoredPrompt]],
        rng: random.Random | None = None,
    ):
        self._db_path = db_path
        self._subjects = (rng or random.Random()).sample(subjects, len(subjects))
        self._target = min(target, len(subjects))
        self._generate_batch = generate_batch
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.stored = 0
        self.requests = 0

    def start(self) -> None:
        if self._target <= 0:
            return
        logger.info("Pre-generating %d fallback prompts in one request", self._target)
        self._thread = threading.Thread(target=self._run, name="prompt-warmer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def _enough(self) -> bool:
        # After the first request, half or more usable is good enough to not spend another.
        return self.requests > 0 and self.stored * 2 >= self._target

    def _run(self) -> None:
        pending = self._subjects[: self._target]
        while pending and self.requests < MAX_WARM_UP_REQUESTS and not self._enough():
            if self._stop.is_set():
                return
            self.requests += 1
            try:
                results = self._generate_batch(pending)
            except llm.LLMError as exc:
                logger.warning("Warm-up request %d failed: %s", self.requests, exc)
                continue
            except Exception:
                logger.exception("Unexpected warm-up failure")
                continue
            if self._stop.is_set():
                return
            with closing(connect(self._db_path)) as db:
                for prompt in results:
                    save(db, prompt)
            self.stored += len(results)
            done = {prompt.subject for prompt in results}
            pending = [subject for subject in pending if subject not in done]
        logger.info(
            "Prompt warm-up finished: %d/%d stored using %d request(s)", self.stored, self._target, self.requests
        )
