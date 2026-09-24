"""One real request to OpenRouter (free models router).

Opt in with RUN_LIVE_LLM=1 (needs OPENROUTER_API_KEY). The conftest guard limits this to exactly one
request (no retries), so running it costs one request from the daily free-model quota.
"""

import os

import pytest

from app import prompts

pytestmark = [
    pytest.mark.skipif(os.environ.get("RUN_LIVE_LLM") != "1", reason="set RUN_LIVE_LLM=1 to run"),
    pytest.mark.live_llm,
]


def test_live_prompt_generation(openrouter_calls):
    results = prompts.generate_batch(["A Rainy Day", "A Map"])
    assert len(openrouter_calls) == 1
    assert results, "the batch came back with no usable prompts"
    for prompt in results:
        assert prompt.subject in {"A Rainy Day", "A Map"}
        assert len(prompt.prompt) > 20
        assert len(prompt.example.split()) > 30
