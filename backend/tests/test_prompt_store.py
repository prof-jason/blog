import importlib
import random
import threading
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import config, llm, prompt_store, prompts
from app.db import connect, init_db
from app.main import create_app
from app.prompt_store import PromptWarmer, StoredPrompt, find_fallback, load_subjects, save
from app.prompts import GeneratedPrompt

SUBJECTS = ["Oceans", "Cities", "Forests", "Deserts"]


@pytest.fixture
def db(db_path):
    init_db(db_path)
    with closing(connect(db_path)) as conn:
        yield conn


def fake_generate(subject):
    return GeneratedPrompt(prompt=f"Write about {subject}.", example=f"An example about {subject}.")


def stored_rows(db):
    return [tuple(row) for row in db.execute("SELECT subject, prompt, example FROM stored_prompts")]


# --- Lookup ---------------------------------------------------------------


def test_find_fallback_prefers_the_requested_subject(db):
    for subject in SUBJECTS:
        save(db, StoredPrompt(subject=subject, prompt=f"P {subject}", example="E"))
    for _ in range(10):
        assert find_fallback(db, "Forests").subject == "Forests"


def test_find_fallback_uses_any_stored_prompt_for_other_subjects(db):
    save(db, StoredPrompt(subject="Oceans", prompt="P", example="E"))
    assert find_fallback(db, "Volcanoes") == StoredPrompt(subject="Oceans", prompt="P", example="E")


def test_find_fallback_returns_none_when_empty(db):
    assert find_fallback(db, "Oceans") is None


def test_load_subjects(tmp_path):
    path = tmp_path / "subjects.json"
    path.write_text('["Oceans", "  Cities ", "", 7]')
    assert load_subjects(path) == ["Oceans", "Cities"]
    assert load_subjects(tmp_path / "missing.json") == []


def test_warm_up_count_defaults_to_10(monkeypatch):
    monkeypatch.delenv("PROMPT_WARM_UP_COUNT", raising=False)
    assert importlib.reload(config).WARM_UP_COUNT == 10
    monkeypatch.setenv("PROMPT_WARM_UP_COUNT", "3")
    assert importlib.reload(config).WARM_UP_COUNT == 3
    monkeypatch.delenv("PROMPT_WARM_UP_COUNT")
    importlib.reload(config)


def test_shared_subjects_file_is_readable():
    subjects = load_subjects(config.SUBJECTS_PATH)
    assert len(subjects) >= 10
    assert len(set(subjects)) == len(subjects)


# --- Endpoint fallback ----------------------------------------------------


@pytest.fixture
def failing_llm(monkeypatch):
    def boom(messages, response_model):
        raise llm.LLMError("Service temporarily overloaded")

    monkeypatch.setattr(llm, "structured_completion", boom)


def _store(db_path, subject, prompt="Stored prompt.", example="Stored example."):
    with closing(connect(db_path)) as conn:
        save(conn, StoredPrompt(subject=subject, prompt=prompt, example=example))


def test_serves_stored_prompt_for_same_subject_when_llm_fails(client, db_path, failing_llm):
    _store(db_path, "Cities", prompt="City prompt.")
    _store(db_path, "Oceans", prompt="Ocean prompt.", example="Ocean example.")

    response = client.post("/api/prompts", json={"subject": "Oceans"})

    assert response.status_code == 200
    assert response.json() == {
        "subject": "Oceans",
        "prompt": "Ocean prompt.",
        "example": "Ocean example.",
        "source": "stored",
    }


def test_serves_another_subjects_prompt_when_none_match(client, db_path, failing_llm):
    _store(db_path, "Cities", prompt="City prompt.")

    body = client.post("/api/prompts", json={"subject": "Oceans"}).json()

    assert body["source"] == "stored"
    assert body["subject"] == "Cities"
    assert body["prompt"] == "City prompt."


def test_returns_502_when_llm_fails_and_nothing_is_stored(client, failing_llm):
    assert client.post("/api/prompts", json={"subject": "Oceans"}).status_code == 502


def test_prefers_live_generation_over_stored_prompts(client, db_path, monkeypatch):
    _store(db_path, "Oceans")
    monkeypatch.setattr(prompts, "generate_for_subject", fake_generate)

    body = client.post("/api/prompts", json={"subject": "Oceans"}).json()

    assert body["source"] == "live"
    assert body["prompt"] == "Write about Oceans."


# --- Warm-up --------------------------------------------------------------


def fake_batch(subjects):
    return [StoredPrompt(subject=s, **fake_generate(s).model_dump()) for s in subjects]


class BatchRecorder:
    """A generate_batch stand-in: replies[i] decides what request i returns (or raises)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[list[str]] = []

    def __call__(self, subjects):
        self.requests.append(list(subjects))
        reply = self.replies[len(self.requests) - 1]
        if isinstance(reply, Exception):
            raise reply
        return fake_batch(subjects[:reply])  # reply = how many of the requested come back usable


def run_warmer(db_path, generate_batch, target=4, subjects=SUBJECTS):
    warmer = PromptWarmer(db_path, subjects, target=target, generate_batch=generate_batch, rng=random.Random(1))
    warmer.start()
    warmer.join(timeout=5)
    return warmer


def test_warmer_stores_every_prompt_from_a_single_request(db, db_path):
    batch = BatchRecorder(4)
    warmer = run_warmer(db_path, batch)

    assert len(batch.requests) == 1
    assert sorted(batch.requests[0]) == sorted(SUBJECTS)  # all asked for at once
    assert warmer.stored == 4
    rows = stored_rows(db)
    assert sorted(subject for subject, _, _ in rows) == sorted(SUBJECTS)
    for subject, prompt, example in rows:
        assert (prompt, example) == (f"Write about {subject}.", f"An example about {subject}.")


def test_warmer_keeps_a_partial_batch_when_at_least_half_is_usable(db, db_path):
    batch = BatchRecorder(2)  # 2 of 4 usable = half: good enough
    warmer = run_warmer(db_path, batch)
    assert len(batch.requests) == 1
    assert warmer.stored == 2


def test_warmer_asks_once_more_for_only_the_missing_subjects(db, db_path):
    batch = BatchRecorder(1, 3)  # 1 of 4 usable: less than half, so one more request
    warmer = run_warmer(db_path, batch)

    assert len(batch.requests) == 2
    first, second = batch.requests
    assert len(second) == 3 and set(second) == set(first) - {first[0]}
    assert warmer.stored == 4
    assert len({subject for subject, _, _ in stored_rows(db)}) == 4


def test_warmer_retries_once_after_a_failed_request(db, db_path):
    batch = BatchRecorder(llm.LLMError("overloaded"), 4)
    warmer = run_warmer(db_path, batch)
    assert len(batch.requests) == 2
    assert warmer.stored == 4


def test_warmer_never_makes_more_than_two_requests(db, db_path):
    batch = BatchRecorder(llm.LLMError("down"), llm.LLMError("down"), 4)
    warmer = run_warmer(db_path, batch)
    assert len(batch.requests) == prompt_store.MAX_WARM_UP_REQUESTS == 2
    assert warmer.stored == 0
    assert stored_rows(db) == []


def test_warmer_survives_unexpected_errors(db, db_path):
    batch = BatchRecorder(ValueError("bug"), 4)
    warmer = run_warmer(db_path, batch)
    assert warmer.stored == 4
    assert not warmer._thread.is_alive()


def test_warmer_caps_target_at_one_prompt_per_subject(db, db_path):
    batch = BatchRecorder(10)
    warmer = run_warmer(db_path, batch, target=10)
    assert len(batch.requests[0]) == len(SUBJECTS)
    assert warmer.stored == len(SUBJECTS)


def test_warmer_does_not_save_after_stop(db, db_path):
    release = threading.Event()

    def slow(subjects):
        release.wait(5)
        return fake_batch(subjects)

    warmer = PromptWarmer(db_path, SUBJECTS, target=3, generate_batch=slow)
    warmer.start()
    warmer.stop()
    release.set()
    warmer.join(timeout=5)
    assert stored_rows(db) == []


@pytest.mark.parametrize("subjects, target", [([], 10), (SUBJECTS, 0)])
def test_warmer_does_nothing_without_subjects_or_target(db_path, subjects, target):
    batch = BatchRecorder()
    warmer = PromptWarmer(db_path, subjects, target=target, generate_batch=batch)
    warmer.start()
    assert warmer._thread is None
    assert batch.requests == []


# --- Startup integration ----------------------------------------------------


def test_startup_pre_generates_prompts_in_background(db_path, static_dir, tmp_path, monkeypatch):
    subjects_path = tmp_path / "subjects.json"
    subjects_path.write_text('["Oceans", "Cities", "Forests", "Deserts"]')
    release = threading.Event()

    requests = []

    def gated(subjects):
        requests.append(subjects)
        release.wait(5)
        return fake_batch(subjects)

    monkeypatch.setattr(prompts, "generate_batch", gated)
    app = create_app(db_path=db_path, static_dir=static_dir, subjects_path=subjects_path, warm_up_count=4)

    with TestClient(app) as client:
        # Startup finished and the API is usable before any prompt is generated.
        assert client.get("/api/health").json()["stored_prompts"] == 0

        release.set()
        app.state.prompt_warmer.join(timeout=5)
        assert client.get("/api/health").json()["stored_prompts"] == 4
        assert len(requests) == 1  # all four from one request

        # The pre-generated prompts now back up a failing LLM.
        def down(subject):
            raise llm.LLMError("overloaded")

        monkeypatch.setattr(prompts, "generate_for_subject", down)
        body = client.post("/api/prompts", json={"subject": "Forests"}).json()
        assert body == {**fake_generate("Forests").model_dump(), "subject": "Forests", "source": "stored"}


def test_stored_prompts_are_wiped_on_restart(db_path, static_dir, tmp_path):
    init_db(db_path)
    with closing(connect(db_path)) as conn:
        save(conn, StoredPrompt(subject="Oceans", prompt="P", example="E"))

    with TestClient(create_app(db_path=db_path, static_dir=static_dir, warm_up_count=0)) as client:
        assert client.get("/api/health").json()["stored_prompts"] == 0
