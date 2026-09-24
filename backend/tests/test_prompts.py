from types import SimpleNamespace

import pytest

from app import llm
from app.prompts import GeneratedPrompt


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def fake(messages, response_model):
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
    def boom(messages, response_model):
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
