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


def test_structured_completion_uses_cerebras_and_parses(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"prompt": "P", "example": "E"}')

    monkeypatch.setattr(llm, "completion", fake_completion)
    result = llm.structured_completion([{"role": "user", "content": "hi"}], GeneratedPrompt)

    assert result == GeneratedPrompt(prompt="P", example="E")
    assert captured["model"] == "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    assert captured["extra_body"] == {"provider": {"order": ["cerebras"]}}
    assert captured["response_format"] is GeneratedPrompt
    assert captured["reasoning_effort"] == "low"
    assert captured["num_retries"] == 3
    assert captured["retry_strategy"] == "exponential_backoff_retry"


@pytest.mark.parametrize("content", ["not json", '{"prompt": "only prompt"}', None])
def test_structured_completion_wraps_bad_output(monkeypatch, content):
    monkeypatch.setattr(llm, "completion", lambda **_: _fake_response(content))
    with pytest.raises(llm.LLMError):
        llm.structured_completion([], GeneratedPrompt)


def test_structured_completion_wraps_provider_errors(monkeypatch):
    def raise_error(**_):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(llm, "completion", raise_error)
    with pytest.raises(llm.LLMError, match="rate limited"):
        llm.structured_completion([], GeneratedPrompt)


def test_retry_dependency_is_installed():
    # LiteLLM's num_retries needs tenacity; without it every retryable error fails outright.
    import tenacity  # noqa: F401
