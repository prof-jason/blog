import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import create_app

pytest_plugins = ["pytester"]

LIVE_MARKER = "live_llm"


@pytest.fixture(autouse=True)
def openrouter_calls(request, monkeypatch):
    """Guards the OpenRouter free-tier daily quota.

    Tests must not reach OpenRouter unless marked `live_llm`. A live test gets exactly one real
    request, with LiteLLM's retries and our bad-output retry turned off, so a failure can't fan out
    into several requests. Yields the list of attempted calls.
    """
    calls = []
    live = request.node.get_closest_marker(LIVE_MARKER) is not None
    real_completion = llm.completion

    def guarded(**kwargs):
        calls.append(kwargs)
        if not live:
            raise AssertionError("Tests must not call OpenRouter: mock llm.completion or mark the test live_llm")
        if len(calls) > 1:
            raise AssertionError("A live_llm test may make only one OpenRouter request")
        return real_completion(**kwargs | {"num_retries": 0})  # whatever the caller asked for

    monkeypatch.setattr(llm, "completion", guarded)
    if live:
        monkeypatch.setattr(llm, "NUM_RETRIES", 0)
        monkeypatch.setattr(llm, "MAX_PARSE_ATTEMPTS", 1)
    yield calls
    # llm wraps errors in LLMError, which the API may turn into a fallback, so check here as well.
    if not live and calls:
        pytest.fail(f"Test attempted {len(calls)} real OpenRouter call(s); mock llm.completion instead")


@pytest.fixture
def static_dir(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "index.html").write_text("<html><body>Prompt Generator</body></html>")
    return out


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "data" / "app.db"


@pytest.fixture
def client(db_path, static_dir):
    with TestClient(create_app(db_path=db_path, static_dir=static_dir, batch_size=0)) as test_client:
        yield test_client
