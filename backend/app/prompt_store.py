"""The prompt pool: every roll is served from here, and it refills itself in the background.

Rolls never call the LLM, so a roll is instant and costs no quota. The pool is filled at startup and
refilled when it runs low, one batch request (about 10 prompts) at a time, and every request is
charged to a daily RequestBudget. Once the budget is spent, rolls keep working by re-serving the
least-served prompts.
"""

import json
import logging
import random
import sqlite3
import threading
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel

from app import llm
from app.budget import RequestBudget
from app.db import connect

logger = logging.getLogger(__name__)

# A refill makes one batch request, plus one more if fewer than half its prompts came back usable.
MAX_REQUESTS_PER_REFILL = 2
# After a refill that stored nothing (e.g. the provider is down), wait before trying again so an
# outage can't burn through the daily budget.
FAILED_REFILL_COOLDOWN_SECONDS = 60
# While a refill is running, clients waiting on an empty pool retry after this long.
RETRY_WHILE_REFILLING_SECONDS = 3


class StoredPrompt(BaseModel):
    subject: str
    prompt: str
    example: str


def load_subjects(path: Path) -> list[str]:
    try:
        subjects = json.loads(path.read_text())
    except FileNotFoundError:
        logger.warning("Subjects file %s not found; the prompt pool will stay empty", path)
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


def count_unserved(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM stored_prompts WHERE served_count = 0").fetchone()[0]


def take_next(db: sqlite3.Connection, exclude: str | None = None) -> StoredPrompt | None:
    """The next prompt to show, marked as served.

    Prefers a subject other than `exclude` (the one on the card now), then the least-served prompt,
    at random among ties. Returns None only if the pool is empty.
    """
    row = db.execute(
        "SELECT id, subject, prompt, example FROM stored_prompts "
        "ORDER BY (subject = ?) ASC, served_count ASC, RANDOM() LIMIT 1",
        (exclude or "",),
    ).fetchone()
    if row is None:
        return None
    db.execute("UPDATE stored_prompts SET served_count = served_count + 1 WHERE id = ?", (row["id"],))
    db.commit()
    return StoredPrompt(subject=row["subject"], prompt=row["prompt"], example=row["example"])


def subjects_to_fill(db: sqlite3.Connection, subjects: list[str], n: int, rng: random.Random) -> list[str]:
    """Up to `n` subjects, those with the fewest stored prompts first (random among ties)."""
    stored = dict(db.execute("SELECT subject, COUNT(*) FROM stored_prompts GROUP BY subject").fetchall())
    shuffled = rng.sample(subjects, len(subjects))
    return sorted(shuffled, key=lambda subject: stored.get(subject, 0))[:n]


class PromptPool:
    """Keeps the pool stocked: one background refill at a time, charged to the request budget."""

    def __init__(
        self,
        db_path: Path,
        subjects: list[str],
        generate_batch: Callable[[list[str]], list[StoredPrompt]],
        budget: RequestBudget,
        batch_size: int,
        refill_below: int,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._db_path = db_path
        self._subjects = subjects
        self._generate_batch = generate_batch
        self.budget = budget
        self._batch_size = min(batch_size, len(subjects))
        self._refill_below = refill_below
        self._rng = rng or random.Random()
        self._clock = clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._refilling = False
        self._cooldown_until = 0.0
        self._budget_warned = False
        self.requests = 0

    @property
    def refilling(self) -> bool:
        return self._refilling

    def start(self) -> None:
        """Fills the empty pool at startup (in the background)."""
        self.refill_if_low()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def retry_after(self) -> int | None:
        """Seconds a client should wait before asking again if the pool is empty, or None if no
        prompts are on the way (the daily budget is spent)."""
        if self._refilling:
            return RETRY_WHILE_REFILLING_SECONDS
        cooldown = self._cooldown_until - self._clock()
        if cooldown > 0:
            return int(cooldown) + 1
        return None

    def refill_if_low(self) -> bool:
        """Starts a background refill if the pool is low and one is allowed. Returns True if started."""
        with self._lock:
            if self._refilling or self._stop.is_set() or self._batch_size <= 0:
                return False
            if self._clock() < self._cooldown_until:
                return False
            with closing(connect(self._db_path)) as db:
                if count_unserved(db) >= self._refill_below:
                    return False
            if self.budget.remaining() == 0:
                if not self._budget_warned:
                    self._budget_warned = True
                    logger.warning(
                        "Daily LLM request budget (%d) is used up; re-serving saved prompts until it frees up",
                        self.budget.limit,
                    )
                return False
            self._budget_warned = False
            self._refilling = True
            self._thread = threading.Thread(target=self._refill, name="prompt-refill", daemon=True)
            self._thread.start()
            return True

    def _refill(self) -> None:
        stored = requests = 0
        try:
            with closing(connect(self._db_path)) as db:
                pending = subjects_to_fill(db, self._subjects, self._batch_size, self._rng)
            logger.info("Generating %d prompts (%d requests left today)", len(pending), self.budget.remaining())
            # A second request only if the first stored fewer than half of the batch.
            while pending and requests < MAX_REQUESTS_PER_REFILL and not (requests and stored * 2 >= self._batch_size):
                if self._stop.is_set() or not self.budget.try_spend():
                    break
                requests += 1
                self.requests += 1
                try:
                    results = self._generate_batch(pending)
                except llm.LLMError as exc:
                    logger.warning("Prompt generation request failed: %s", exc)
                    continue
                if self._stop.is_set():
                    return
                with closing(connect(self._db_path)) as db:
                    for prompt in results:
                        save(db, prompt)
                stored += len(results)
                done = {prompt.subject for prompt in results}
                pending = [subject for subject in pending if subject not in done]
        except Exception:
            logger.exception("Unexpected failure while refilling the prompt pool")
        finally:
            with self._lock:
                if stored == 0 and requests > 0:
                    self._cooldown_until = self._clock() + FAILED_REFILL_COOLDOWN_SECONDS
                self._refilling = False
            logger.info("Refill finished: %d prompts stored using %d request(s)", stored, requests)
