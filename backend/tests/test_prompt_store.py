import importlib
import json
import random
import threading
import time
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import config, llm, prompt_store, prompts
from app.budget import RequestBudget
from app.db import connect, init_db
from app.main import create_app
from app.prompt_store import (
    PromptPool,
    StoredPrompt,
    count_unserved,
    load_subjects,
    save,
    subjects_to_fill,
    take_next,
)

SUBJECTS = ["Oceans", "Cities", "Forests", "Deserts"]


@pytest.fixture
def db(db_path):
    init_db(db_path)
    with closing(connect(db_path)) as conn:
        yield conn


def fake_batch(subjects):
    return [StoredPrompt(subject=s, prompt=f"Write about {s}.", example=f"An example about {s}.") for s in subjects]


def stored_subjects(db):
    return sorted(row[0] for row in db.execute("SELECT subject FROM stored_prompts"))


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class BatchRecorder:
    """A generate_batch stand-in: replies[i] is how many prompts request i returns, or an exception."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[list[str]] = []

    def __call__(self, subjects):
        self.requests.append(list(subjects))
        reply = self.replies[len(self.requests) - 1]
        if isinstance(reply, BaseException):
            raise reply
        return fake_batch(subjects[:reply])


def make_pool(db_path, generate, *, limit=40, batch_size=4, refill_below=2, clock=None, subjects=SUBJECTS):
    return PromptPool(
        db_path,
        subjects,
        generate_batch=generate,
        budget=RequestBudget(limit, clock=clock or FakeClock()),
        batch_size=batch_size,
        refill_below=refill_below,
        rng=random.Random(1),
        clock=clock or FakeClock(),
    )


def run(pool):
    started = pool.refill_if_low()
    pool.join(timeout=5)
    return started


# --- Store ----------------------------------------------------------------------


def test_take_next_avoids_the_current_subject_and_marks_prompts_served(db):
    for subject in SUBJECTS:
        save(db, StoredPrompt(subject=subject, prompt=f"P {subject}", example="E"))

    for _ in range(20):
        assert take_next(db, exclude="Oceans").subject != "Oceans"
    assert count_unserved(db) == 1  # only Oceans was never served


def test_take_next_serves_the_least_served_prompts_first(db):
    for subject in SUBJECTS:
        save(db, StoredPrompt(subject=subject, prompt="P", example="E"))
    first_four = {take_next(db).subject for _ in range(4)}
    assert first_four == set(SUBJECTS)  # every prompt once before any repeats


def test_take_next_repeats_the_subject_only_if_nothing_else_exists(db):
    save(db, StoredPrompt(subject="Oceans", prompt="P", example="E"))
    assert take_next(db, exclude="Oceans").subject == "Oceans"


def test_take_next_returns_none_for_an_empty_pool(db):
    assert take_next(db) is None


def test_subjects_to_fill_prefers_the_least_stocked_subjects(db):
    for subject in ["Oceans", "Oceans", "Cities"]:
        save(db, StoredPrompt(subject=subject, prompt="P", example="E"))
    assert set(subjects_to_fill(db, SUBJECTS, 2, random.Random(0))) == {"Forests", "Deserts"}


def test_load_subjects(tmp_path):
    path = tmp_path / "subjects.json"
    path.write_text('["Oceans", "  Cities ", "", 7]')
    assert load_subjects(path) == ["Oceans", "Cities"]
    assert load_subjects(tmp_path / "missing.json") == []


def test_shared_subjects_file_is_readable():
    subjects = load_subjects(config.SUBJECTS_PATH)
    assert len(subjects) >= 10
    assert len(set(subjects)) == len(subjects)
    assert all(len(subject) <= 80 for subject in subjects)


def test_pool_settings_defaults(monkeypatch):
    for name in ["PROMPT_BATCH_SIZE", "PROMPT_REFILL_BELOW", "LLM_DAILY_REQUEST_LIMIT"]:
        monkeypatch.delenv(name, raising=False)
    reloaded = importlib.reload(config)
    assert (reloaded.BATCH_SIZE, reloaded.REFILL_BELOW, reloaded.DAILY_REQUEST_LIMIT) == (10, 5, 40)
    monkeypatch.setenv("LLM_DAILY_REQUEST_LIMIT", "900")
    assert importlib.reload(config).DAILY_REQUEST_LIMIT == 900
    monkeypatch.delenv("LLM_DAILY_REQUEST_LIMIT")
    importlib.reload(config)


# --- Refilling --------------------------------------------------------------------


def test_refill_fills_a_whole_batch_with_one_request(db, db_path):
    batch = BatchRecorder(4)
    pool = make_pool(db_path, batch)

    assert run(pool)
    assert len(batch.requests) == 1
    assert sorted(batch.requests[0]) == sorted(SUBJECTS)
    assert stored_subjects(db) == sorted(SUBJECTS)
    assert not pool.refilling


def test_refill_asks_once_more_for_only_the_missing_subjects(db, db_path):
    batch = BatchRecorder(1, 3)  # 1 of 4 usable is less than half
    run(make_pool(db_path, batch))

    first, second = batch.requests
    assert len(second) == 3 and set(second) == set(first) - {first[0]}
    assert stored_subjects(db) == sorted(SUBJECTS)


def test_refill_keeps_a_batch_that_is_at_least_half_usable(db, db_path):
    batch = BatchRecorder(2)
    run(make_pool(db_path, batch))
    assert len(batch.requests) == 1
    assert len(stored_subjects(db)) == 2


def test_refill_makes_at_most_two_requests(db, db_path):
    batch = BatchRecorder(llm.LLMError("down"), llm.LLMError("down"), 4)
    run(make_pool(db_path, batch))
    assert len(batch.requests) == prompt_store.MAX_REQUESTS_PER_REFILL == 2
    assert stored_subjects(db) == []


def test_refill_only_when_the_pool_runs_low(db, db_path):
    batch = BatchRecorder(4, 4)
    pool = make_pool(db_path, batch, refill_below=2)
    run(pool)  # 4 unserved

    assert not run(pool)
    take_next(db), take_next(db), take_next(db)  # 1 unserved left
    assert run(pool)
    assert len(batch.requests) == 2


def test_only_one_refill_runs_at_a_time(db, db_path):
    release = threading.Event()

    def slow(subjects):
        release.wait(5)
        return fake_batch(subjects)

    pool = make_pool(db_path, slow)
    assert pool.refill_if_low()
    assert pool.refilling
    assert not pool.refill_if_low()
    release.set()
    pool.join(timeout=5)
    assert not pool.refilling


def test_a_failed_refill_cools_down_before_trying_again(db, db_path):
    clock = FakeClock()
    batch = BatchRecorder(llm.LLMError("down"), llm.LLMError("down"), 4)
    pool = make_pool(db_path, batch, clock=clock)
    run(pool)

    assert not run(pool)  # still cooling down: no requests spent
    assert len(batch.requests) == 2
    assert pool.retry_after() == prompt_store.FAILED_REFILL_COOLDOWN_SECONDS + 1

    clock.now += prompt_store.FAILED_REFILL_COOLDOWN_SECONDS
    assert run(pool)
    assert stored_subjects(db) == sorted(SUBJECTS)


def test_every_request_is_charged_to_the_daily_budget(db, db_path):
    batch = BatchRecorder(1, 1, 4)
    pool = make_pool(db_path, batch, limit=2)
    run(pool)  # spends both requests (1 usable, then 1 more)

    assert pool.budget.remaining() == 0
    take_next(db), take_next(db)
    assert not run(pool)  # low, but no budget left
    assert len(batch.requests) == 2
    assert pool.retry_after() is None


def test_a_refill_stops_when_the_budget_runs_out_midway(db, db_path):
    batch = BatchRecorder(0, 4)
    run(make_pool(db_path, batch, limit=1))
    assert len(batch.requests) == 1


def test_refill_survives_unexpected_errors(db, db_path):
    pool = make_pool(db_path, BatchRecorder(ValueError("bug")))
    run(pool)
    assert not pool.refilling


def test_nothing_is_saved_after_stop(db, db_path):
    release = threading.Event()

    def slow(subjects):
        release.wait(5)
        return fake_batch(subjects)

    pool = make_pool(db_path, slow)
    pool.refill_if_low()
    pool.stop()
    release.set()
    pool.join(timeout=5)
    assert stored_subjects(db) == []
    assert not pool.refill_if_low()


@pytest.mark.parametrize("subjects, batch_size", [([], 10), (SUBJECTS, 0)])
def test_no_refills_without_subjects_or_batch_size(db, db_path, subjects, batch_size):
    batch = BatchRecorder()
    pool = make_pool(db_path, batch, subjects=subjects, batch_size=batch_size)
    assert not pool.refill_if_low()
    assert batch.requests == []


# --- The /api/prompts/next endpoint ----------------------------------------------


@pytest.fixture
def subjects_path(tmp_path):
    path = tmp_path / "subjects.json"
    path.write_text(json.dumps(SUBJECTS))
    return path


def pool_app(db_path, static_dir, subjects_path, **settings):
    return create_app(db_path=db_path, static_dir=static_dir, subjects_path=subjects_path, **settings)


def test_next_serves_from_the_pool_without_calling_the_llm(
    db_path, static_dir, subjects_path, monkeypatch, openrouter_calls
):
    monkeypatch.setattr(prompts, "generate_batch", fake_batch)
    app = pool_app(db_path, static_dir, subjects_path, batch_size=4, refill_below=1)
    with TestClient(app) as client:
        app.state.prompt_pool.join(timeout=5)

        body = client.get("/api/prompts/next", params={"exclude": "Oceans"}).json()

        assert body["subject"] in SUBJECTS and body["subject"] != "Oceans"
        assert body == {**fake_batch([body["subject"]])[0].model_dump()}
        assert client.get("/api/health").json()["unserved_prompts"] == 3
    assert openrouter_calls == []


def test_next_returns_503_with_retry_after_while_the_pool_is_being_filled(
    db_path, static_dir, subjects_path, monkeypatch
):
    release = threading.Event()

    def slow(subjects):
        release.wait(5)
        return fake_batch(subjects)

    monkeypatch.setattr(prompts, "generate_batch", slow)
    app = pool_app(db_path, static_dir, subjects_path, batch_size=4)
    with TestClient(app) as client:
        response = client.get("/api/prompts/next")
        assert response.status_code == 503
        assert response.headers["retry-after"] == str(prompt_store.RETRY_WHILE_REFILLING_SECONDS)

        release.set()
        app.state.prompt_pool.join(timeout=5)
        assert client.get("/api/prompts/next").status_code == 200


def test_next_returns_503_without_retry_after_when_the_budget_is_spent(
    db_path, static_dir, subjects_path, monkeypatch
):
    monkeypatch.setattr(prompts, "generate_batch", fake_batch)
    app = pool_app(db_path, static_dir, subjects_path, batch_size=4, daily_request_limit=0)
    with TestClient(app) as client:
        response = client.get("/api/prompts/next")
        assert response.status_code == 503
        assert "retry-after" not in response.headers


def test_next_stays_instant_while_a_refill_is_stuck(db_path, static_dir, subjects_path, monkeypatch):
    """No request ever waits on the LLM, so a hung provider can't tie up the server."""
    release = threading.Event()
    calls = []

    def first_fast_then_stuck(subjects):
        calls.append(subjects)
        if len(calls) > 1:
            release.wait(10)
        return fake_batch(subjects)

    monkeypatch.setattr(prompts, "generate_batch", first_fast_then_stuck)
    app = pool_app(db_path, static_dir, subjects_path, batch_size=4, refill_below=3)
    try:
        with TestClient(app) as client:
            app.state.prompt_pool.join(timeout=5)
            started = time.monotonic()
            statuses = [client.get("/api/prompts/next").status_code for _ in range(40)]
            assert time.monotonic() - started < 2
            assert statuses == [200] * 40  # re-serving saved prompts while the refill hangs
            assert app.state.prompt_pool.refilling
    finally:
        release.set()


def test_heavy_rolling_stays_within_the_daily_budget(db_path, static_dir, subjects_path, monkeypatch):
    calls = []

    def counted(subjects):
        calls.append(subjects)
        return fake_batch(subjects)

    monkeypatch.setattr(prompts, "generate_batch", counted)
    app = pool_app(db_path, static_dir, subjects_path, batch_size=2, refill_below=1, daily_request_limit=3)
    with TestClient(app) as client:
        for _ in range(300):
            assert client.get("/api/prompts/next").status_code in (200, 503)
            app.state.prompt_pool.join(timeout=5)
        assert client.get("/api/prompts/next").status_code == 200  # still serving saved prompts
    assert len(calls) == 3


def test_stored_prompts_are_wiped_on_restart(db_path, static_dir, subjects_path):
    init_db(db_path)
    with closing(connect(db_path)) as conn:
        save(conn, StoredPrompt(subject="Oceans", prompt="P", example="E"))

    with TestClient(pool_app(db_path, static_dir, subjects_path, batch_size=0)) as client:
        assert client.get("/api/health").json()["stored_prompts"] == 0
