"""The conftest guard that keeps tests from spending the OpenRouter free-tier quota."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app import llm

CONFTEST = (Path(__file__).parent / "conftest.py").read_text()
VALID = '{"prompt": "P", "example": "E"}'


@pytest.fixture
def fake_openrouter(monkeypatch):
    """Stands in for the real network call the guard wraps, and counts requests."""
    requests = []

    def fake(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=VALID))])

    monkeypatch.setattr(llm, "completion", fake)
    return requests


def run(pytester, test_source):
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(test_source)
    return pytester.runpytest_inprocess("-p", "no:cacheprovider", "-W", "ignore::pytest.PytestUnknownMarkWarning")


def test_unmarked_test_cannot_reach_openrouter(pytester, fake_openrouter):
    result = run(
        pytester,
        """
from app import llm
from app.prompts import GeneratedPrompt

def test_forgot_to_mock():
    try:
        llm.structured_completion([], GeneratedPrompt)
    except llm.LLMError:
        pass  # even if the error is swallowed, the guard fails the test
""",
    )
    result.assert_outcomes(passed=1, errors=1)  # body passes, guard errors at teardown
    result.stdout.fnmatch_lines(["*attempted 1 real OpenRouter call*"])
    assert fake_openrouter == []


def test_unmarked_test_through_the_api_is_caught_even_with_a_fallback(pytester, fake_openrouter):
    result = run(
        pytester,
        """
from app.prompts import generate_for_subject
from app import llm

def test_endpoint_style_call():
    try:
        generate_for_subject("Oceans")
    except llm.LLMError:
        pass
""",
    )
    result.assert_outcomes(passed=1, errors=1)  # body passes, guard errors at teardown
    assert fake_openrouter == []


def test_live_test_makes_exactly_one_request_without_retries(pytester, fake_openrouter):
    result = run(
        pytester,
        """
import pytest
from app import llm
from app.prompts import GeneratedPrompt

@pytest.mark.live_llm
def test_live(openrouter_calls):
    assert llm.NUM_RETRIES == 0 and llm.MAX_PARSE_ATTEMPTS == 1
    assert llm.structured_completion([], GeneratedPrompt) == GeneratedPrompt(prompt="P", example="E")
    assert len(openrouter_calls) == 1
""",
    )
    result.assert_outcomes(passed=1)
    assert len(fake_openrouter) == 1
    assert fake_openrouter[0]["num_retries"] == 0


def test_live_test_cannot_make_a_second_request(pytester, fake_openrouter):
    result = run(
        pytester,
        """
import pytest
from app import llm
from app.prompts import GeneratedPrompt

@pytest.mark.live_llm
def test_greedy_live():
    llm.structured_completion([], GeneratedPrompt)
    with pytest.raises(llm.LLMError, match="only one OpenRouter request"):
        llm.structured_completion([], GeneratedPrompt)
""",
    )
    result.assert_outcomes(passed=1)
    assert len(fake_openrouter) == 1


def test_mocked_tests_are_unaffected(pytester, fake_openrouter):
    result = run(
        pytester,
        """
from app import llm
from app.prompts import GeneratedPrompt

def test_mocked(monkeypatch):
    monkeypatch.setattr(llm, "structured_completion", lambda m, r: r(prompt="x", example="y"))
    assert llm.structured_completion([], GeneratedPrompt).prompt == "x"
""",
    )
    result.assert_outcomes(passed=1)
    assert fake_openrouter == []
