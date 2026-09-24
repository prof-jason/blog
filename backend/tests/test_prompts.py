import json
import threading
import time
from types import SimpleNamespace

import pytest

from app import llm, prompts
from app.prompt_store import StoredPrompt
from app.prompts import GeneratedPrompt


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def fake(messages, response_model, **_):
        calls.append((messages, response_model))
        return GeneratedPrompt(prompt="  Write about the tide.  ", example=" The tide came in slowly. ")

    monkeypatch.setattr(llm, "structured_completion", fake)
    return calls


def test_generates_prompt_for_subject(client, fake_llm):
    response = client.post("/api/prompts", json={"subject": "  The Ocean "})
    assert response.status_code == 200
    assert response.json() == {
        "subject": "The Ocean",
        "prompt": "Write about the tide.",
        "example": "The tide came in slowly.",
        "source": "live",
    }
    messages, model = fake_llm[0]
    assert model is GeneratedPrompt
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "Subject: The Ocean"}


@pytest.mark.parametrize("subject", ["", "   ", "x" * 81])
def test_rejects_invalid_subject(client, fake_llm, subject):
    assert client.post("/api/prompts", json={"subject": subject}).status_code == 422
    assert fake_llm == []


def test_llm_failure_returns_502(client, monkeypatch):
    def boom(messages, response_model, **_):
        raise llm.LLMError("provider down")

    monkeypatch.setattr(llm, "structured_completion", boom)
    response = client.post("/api/prompts", json={"subject": "Weather"})
    assert response.status_code == 502
    assert "try again" in response.json()["detail"]


def _fake_response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_structured_completion_uses_free_router_and_parses(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"prompt": "P", "example": "E"}')

    monkeypatch.setattr(llm, "completion", fake_completion)
    result = llm.structured_completion([{"role": "user", "content": "hi"}], GeneratedPrompt)

    assert result == GeneratedPrompt(prompt="P", example="E")
    assert captured["model"] == "openrouter/openrouter/free"
    assert captured["extra_body"] == {"provider": {"order": ["cerebras"], "require_parameters": True}}
    assert captured["response_format"] is GeneratedPrompt
    assert captured["reasoning_effort"] == "low"
    assert captured["num_retries"] == 3
    assert captured["retry_strategy"] == "exponential_backoff_retry"


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"prompt": "P", "example": "E"}\n```',
        '```\n{"prompt": "P", "example": "E"}\n```',
        'Here you go:\n{"prompt": "P", "example": "E"}\nHope this helps!',
        '  {"prompt": "P", "example": "E"}  ',
    ],
)
def test_structured_completion_tolerates_formatting_from_different_models(monkeypatch, content):
    monkeypatch.setattr(llm, "completion", lambda **_: _fake_response(content))
    assert llm.structured_completion([], GeneratedPrompt) == GeneratedPrompt(prompt="P", example="E")


@pytest.mark.parametrize("content", ["not json", '{"prompt": "only prompt"}', None, ""])
def test_structured_completion_gives_up_on_persistently_bad_output(monkeypatch, content):
    calls = []
    monkeypatch.setattr(llm, "completion", lambda **_: calls.append(1) or _fake_response(content))
    with pytest.raises(llm.LLMError):
        llm.structured_completion([], GeneratedPrompt)
    assert len(calls) == llm.MAX_PARSE_ATTEMPTS


def test_structured_completion_retries_once_after_bad_output(monkeypatch):
    replies = iter(["Sorry, I can't format that.", '{"prompt": "P", "example": "E"}'])
    monkeypatch.setattr(llm, "completion", lambda **_: _fake_response(next(replies)))
    assert llm.structured_completion([], GeneratedPrompt) == GeneratedPrompt(prompt="P", example="E")


def test_structured_completion_does_not_re_retry_provider_errors(monkeypatch):
    calls = []

    def raise_error(**_):
        calls.append(1)
        raise RuntimeError("rate limited")

    monkeypatch.setattr(llm, "completion", raise_error)
    with pytest.raises(llm.LLMError, match="rate limited"):
        llm.structured_completion([], GeneratedPrompt)
    assert len(calls) == 1  # litellm's own num_retries already handled these


@pytest.mark.parametrize(
    "content, expected",
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": {"b": 2}}\n```', '{"a": {"b": 2}}'),
        ('text {"a": 1} text', '{"a": 1}'),
        ("no braces here", "no braces here"),
    ],
)
def test_extract_json(content, expected):
    assert llm.extract_json(content) == expected


def test_retry_dependency_is_installed():
    # LiteLLM's num_retries needs tenacity; without it every retryable error fails outright.
    import tenacity  # noqa: F401


# --- Batch generation (startup warm-up) -------------------------------------


def test_structured_completion_passes_per_call_options(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"prompt": "P", "example": "E"}')

    monkeypatch.setattr(llm, "completion", fake_completion)
    llm.structured_completion([], GeneratedPrompt)
    assert captured["timeout"] == llm.TIMEOUT_SECONDS
    assert "max_tokens" not in captured

    llm.structured_completion([], GeneratedPrompt, max_tokens=123, timeout=9)
    assert (captured["max_tokens"], captured["timeout"]) == (123, 9)


def test_structured_completion_parse_attempts_1_makes_one_request(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "completion", lambda **_: calls.append(1) or _fake_response("garbage"))
    with pytest.raises(llm.UnusableOutputError):
        llm.structured_completion([], GeneratedPrompt, parse_attempts=1)
    assert len(calls) == 1


def _batch_json(*entries):
    return json.dumps({"prompts": [dict(zip(("subject", "prompt", "example"), e)) for e in entries]})


def test_generate_batch_asks_for_every_subject_in_one_request(monkeypatch):
    captured = []

    def fake_completion(**kwargs):
        captured.append(kwargs)
        return _fake_response(_batch_json(("Oceans", "P1", "E1"), ("Cities", "P2", "E2")))

    monkeypatch.setattr(llm, "completion", fake_completion)
    result = prompts.generate_batch(["Oceans", "Cities"])

    assert len(captured) == 1
    user_message = captured[0]["messages"][1]["content"]
    assert "- Oceans" in user_message and "- Cities" in user_message
    assert captured[0]["max_tokens"] == prompts.BATCH_MAX_TOKENS
    assert captured[0]["timeout"] == prompts.BATCH_TIMEOUT_SECONDS
    assert captured[0]["response_format"] is prompts.PromptBatch
    assert result == [
        StoredPrompt(subject="Oceans", prompt="P1", example="E1"),
        StoredPrompt(subject="Cities", prompt="P2", example="E2"),
    ]


def test_generate_batch_keeps_only_usable_entries(monkeypatch):
    reply = _batch_json(
        ("oceans ", " P1 ", " E1 "),  # case/whitespace differences map to the requested subject
        ("Volcanoes", "P", "E"),  # not asked for
        ("Cities", "", "E"),  # blank prompt
        ("Forests", "P", "   "),  # blank example
        ("Oceans", "P again", "E again"),  # duplicate subject: first one wins
    )  # ...and no entry at all for Deserts
    monkeypatch.setattr(llm, "completion", lambda **_: _fake_response(reply))

    result = prompts.generate_batch(["Oceans", "Cities", "Forests", "Deserts"])

    assert result == [StoredPrompt(subject="Oceans", prompt="P1", example="E1")]


def test_generate_batch_tolerates_an_entry_with_missing_fields(monkeypatch):
    reply = '```json\n{"prompts": [{"subject": "Oceans", "prompt": "P1"}, ' \
        '{"subject": "Cities", "prompt": "P2", "example": "E2"}]}\n```'
    monkeypatch.setattr(llm, "completion", lambda **_: _fake_response(reply))
    assert prompts.generate_batch(["Oceans", "Cities"]) == [StoredPrompt(subject="Cities", prompt="P2", example="E2")]


def test_generate_batch_makes_one_request_even_for_unusable_output(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "completion", lambda **_: calls.append(1) or _fake_response("Sorry!"))
    with pytest.raises(llm.LLMError):
        prompts.generate_batch(["Oceans"])
    assert len(calls) == 1  # the warmer, not the wrapper, decides whether to spend another


# --- Falling back on blank replies and on no reply --------------------------


def _store_prompt(client_app_db_path, subject="Oceans"):
    from contextlib import closing

    from app.db import connect
    from app.prompt_store import save

    with closing(connect(client_app_db_path)) as conn:
        save(conn, StoredPrompt(subject=subject, prompt="Stored prompt.", example="Stored example."))


@pytest.mark.parametrize(
    "content",
    ['{"prompt": "", "example": ""}', '{"prompt": "   ", "example": "E"}', '{"prompt": "P", "example": "\\n\\t"}'],
)
def test_blank_reply_falls_back_to_a_stored_prompt(client, db_path, monkeypatch, content):
    _store_prompt(db_path)
    monkeypatch.setattr(llm, "completion", lambda **_: _fake_response(content))

    body = client.post("/api/prompts", json={"subject": "Oceans"}).json()

    assert body["source"] == "stored"
    assert body["prompt"] == "Stored prompt."


def test_blank_reply_with_nothing_stored_is_an_error_not_an_empty_card(client, monkeypatch):
    monkeypatch.setattr(llm, "completion", lambda **_: _fake_response('{"prompt": " ", "example": " "}'))
    assert client.post("/api/prompts", json={"subject": "Oceans"}).status_code == 502


def test_reply_text_is_stripped(monkeypatch):
    monkeypatch.setattr(llm, "completion", lambda **_: _fake_response('{"prompt": "  P \\n", "example": "\\tE "}'))
    assert llm.structured_completion([], GeneratedPrompt) == GeneratedPrompt(prompt="P", example="E")


def test_card_clicks_use_tight_limits_so_abandoned_calls_stay_cheap(monkeypatch):
    captured = []

    def fake_completion(**kwargs):
        captured.append(kwargs)
        return _fake_response("not json")

    monkeypatch.setattr(llm, "completion", fake_completion)
    with pytest.raises(llm.LLMError):
        prompts.generate_for_subject("Oceans")

    assert len(captured) == 1  # bad output falls back instead of re-asking
    assert captured[0]["timeout"] == prompts.LIVE_ATTEMPT_TIMEOUT_SECONDS == 15
    assert captured[0]["num_retries"] == prompts.LIVE_NUM_RETRIES == 1
    assert prompts.LIVE_ATTEMPT_TIMEOUT_SECONDS < prompts.LIVE_DEADLINE_SECONDS


@pytest.fixture
def stuck_provider(monkeypatch):
    """OpenRouter never answers (until the test ends), and the click deadline is shortened."""
    release = threading.Event()

    def hang(**_):
        release.wait(10)
        return _fake_response('{"prompt": "Too late", "example": "Too late"}')

    monkeypatch.setattr(llm, "completion", hang)
    monkeypatch.setattr(prompts, "LIVE_DEADLINE_SECONDS", 0.3)
    yield
    release.set()


def test_no_response_falls_back_at_the_deadline(client, db_path, stuck_provider):
    _store_prompt(db_path)

    started = time.monotonic()
    response = client.post("/api/prompts", json={"subject": "Oceans"})
    elapsed = time.monotonic() - started

    assert response.json()["source"] == "stored"
    assert response.json()["prompt"] == "Stored prompt."
    assert elapsed < 2


def test_no_response_with_nothing_stored_returns_502_at_the_deadline(client, stuck_provider):
    started = time.monotonic()
    assert client.post("/api/prompts", json={"subject": "Oceans"}).status_code == 502
    assert time.monotonic() - started < 2


def test_answer_within_the_deadline_is_served_live(client, monkeypatch):
    monkeypatch.setattr(prompts, "LIVE_DEADLINE_SECONDS", 5)
    monkeypatch.setattr(llm, "completion", lambda **_: _fake_response('{"prompt": "P", "example": "E"}'))
    body = client.post("/api/prompts", json={"subject": "Oceans"}).json()
    assert (body["source"], body["prompt"]) == ("live", "P")


def test_startup_batch_keeps_generous_limits(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"prompts": []}')

    monkeypatch.setattr(llm, "completion", fake_completion)
    prompts.generate_batch(["Oceans"])
    assert captured["num_retries"] == llm.NUM_RETRIES
    assert captured["timeout"] == prompts.BATCH_TIMEOUT_SECONDS


# --- Audience -----------------------------------------------------------------


@pytest.mark.parametrize("system_prompt", [prompts.SYSTEM_PROMPT, prompts.BATCH_SYSTEM_PROMPT])
def test_prompts_target_grades_4_to_6(system_prompt):
    assert "grades 4-6 (ages 9-12)" in system_prompt
    assert "60-100 words" in system_prompt  # example length suited to the grade level
    assert "voice and experiences of a kid" in system_prompt


def test_single_and_batch_prompts_share_the_same_guidelines():
    guidelines = prompts._WRITING_GUIDELINES
    assert guidelines in prompts.SYSTEM_PROMPT
    assert guidelines in prompts.BATCH_SYSTEM_PROMPT


def test_card_click_sends_the_grade_level_guidelines(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"prompt": "P", "example": "E"}')

    monkeypatch.setattr(llm, "completion", fake_completion)
    prompts.generate_for_subject("Oceans")
    assert captured["messages"][0] == {"role": "system", "content": prompts.SYSTEM_PROMPT}
