"""Prompts pre-generated at startup, served when live generation fails."""

import json
import logging
import random
import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from app import llm
from app.db import connect

logger = logging.getLogger(__name__)

WARM_UP_WORKERS = 3
# Stop after this many attempts per target prompt so a dead provider doesn't retry forever.
MAX_ATTEMPTS_PER_PROMPT = 2


class StoredPrompt(BaseModel):
    subject: str
    prompt: str
    example: str


class Generated(Protocol):
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
    """Generates `target` prompts on background threads and stores them."""

    def __init__(
        self,
        db_path: Path,
        subjects: list[str],
        target: int,
        generate: Callable[[str], Generated],
        workers: int = WARM_UP_WORKERS,
        rng: random.Random | None = None,
    ):
        self._db_path = db_path
        self._subjects = (rng or random.Random()).sample(subjects, len(subjects))
        self._target = target if subjects else 0
        self._generate = generate
        self._workers = workers
        self._max_attempts = self._target * MAX_ATTEMPTS_PER_PROMPT
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self.stored = 0
        self.attempts = 0
        self._in_flight = 0
        self._finished = False

    def start(self) -> None:
        if self._target <= 0:
            return
        logger.info("Pre-generating %d fallback prompts", self._target)
        for i in range(min(self._workers, self._target)):
            thread = threading.Thread(target=self._work, name=f"prompt-warmer-{i}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        for thread in self._threads:
            thread.join(timeout)

    def _next_subject(self) -> str | None:
        with self._lock:
            done = self.stored + self._in_flight >= self._target
            if done or self.attempts >= self._max_attempts or self._stop.is_set():
                return None
            subject = self._subjects[self.attempts % len(self._subjects)]
            self.attempts += 1
            self._in_flight += 1
            return subject

    def _work(self) -> None:
        while (subject := self._next_subject()) is not None:
            stored = False
            try:
                result = self._generate(subject)
                if not self._stop.is_set():
                    with closing(connect(self._db_path)) as db:
                        save(db, StoredPrompt(subject=subject, prompt=result.prompt, example=result.example))
                    stored = True
            except llm.LLMError as exc:
                logger.warning("Warm-up generation failed for %r: %s", subject, exc)
            except Exception:
                logger.exception("Unexpected warm-up failure for %r", subject)
            finally:
                with self._lock:
                    self._in_flight -= 1
                    self.stored += stored
        with self._lock:
            if self._in_flight == 0 and not self._finished and not self._stop.is_set():
                self._finished = True
                logger.info("Prompt warm-up finished: %d/%d stored", self.stored, self._target)
