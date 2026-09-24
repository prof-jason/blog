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


def test_warmer_stores_target_number_of_prompts(db, db_path):
    warmer = PromptWarmer(db_path, SUBJECTS, target=3, generate=fake_generate, rng=random.Random(1))
    warmer.start()
    warmer.join(timeout=5)

    rows = stored_rows(db)
    assert len(rows) == 3
    assert warmer.stored == 3
    assert len({subject for subject, _, _ in rows}) == 3  # distinct subjects while they last
    for subject, prompt, example in rows:
        assert subject in SUBJECTS
        assert prompt == f"Write about {subject}."
        assert example == f"An example about {subject}."


def test_warmer_cycles_subjects_when_target_exceeds_them(db, db_path):
    warmer = PromptWarmer(db_path, SUBJECTS, target=10, generate=fake_generate)
    warmer.start()
    warmer.join(timeout=5)
    assert len(stored_rows(db)) == 10


def test_warmer_retries_past_failures_to_reach_target(db, db_path):
    calls = []
    lock = threading.Lock()

    def flaky(subject):
        with lock:
            calls.append(subject)
            fail = len(calls) % 2 == 1  # every other call fails
        if fail:
            raise llm.LLMError("overloaded")
        return fake_generate(subject)

    warmer = PromptWarmer(db_path, SUBJECTS, target=3, generate=flaky, workers=1)
    warmer.start()
    warmer.join(timeout=5)

    assert len(stored_rows(db)) == 3
    assert len(calls) == 6


def test_warmer_gives_up_after_max_attempts_when_provider_is_down(db, db_path):
    def down(subject):
        raise llm.LLMError("overloaded")

    warmer = PromptWarmer(db_path, SUBJECTS, target=5, generate=down)
    warmer.start()
    warmer.join(timeout=5)

    assert stored_rows(db) == []
    assert warmer.attempts == 5 * prompt_store.MAX_ATTEMPTS_PER_PROMPT


def test_warmer_survives_unexpected_errors(db, db_path):
    def broken(subject):
        raise ValueError("bug")

    warmer = PromptWarmer(db_path, SUBJECTS, target=2, generate=broken)
    warmer.start()
    warmer.join(timeout=5)
    assert not any(t.is_alive() for t in warmer._threads)


def test_warmer_does_not_save_after_stop(db, db_path):
    release = threading.Event()

    def slow(subject):
        release.wait(5)
        return fake_generate(subject)

    warmer = PromptWarmer(db_path, SUBJECTS, target=3, generate=slow)
    warmer.start()
    warmer.stop()
    release.set()
    warmer.join(timeout=5)
    assert stored_rows(db) == []


@pytest.mark.parametrize("subjects, target", [([], 10), (SUBJECTS, 0)])
def test_warmer_does_nothing_without_subjects_or_target(db_path, subjects, target):
    warmer = PromptWarmer(db_path, subjects, target=target, generate=fake_generate)
    warmer.start()
    assert warmer._threads == []


# --- Startup integration ----------------------------------------------------


def test_startup_pre_generates_prompts_in_background(db_path, static_dir, tmp_path, monkeypatch):
    subjects_path = tmp_path / "subjects.json"
    subjects_path.write_text('["Oceans", "Cities", "Forests", "Deserts"]')
    release = threading.Event()

    def gated(subject):
        release.wait(5)
        return fake_generate(subject)

    monkeypatch.setattr(prompts, "generate_for_subject", gated)
    app = create_app(db_path=db_path, static_dir=static_dir, subjects_path=subjects_path, warm_up_count=4)

    with TestClient(app) as client:
        # Startup finished and the API is usable before any prompt is generated.
        assert client.get("/api/health").json()["stored_prompts"] == 0

        release.set()
        app.state.prompt_warmer.join(timeout=5)
        assert client.get("/api/health").json()["stored_prompts"] == 4

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
