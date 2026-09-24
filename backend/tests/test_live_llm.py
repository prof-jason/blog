"""One real request to OpenRouter (free models router).

Opt in with RUN_LIVE_LLM=1 (needs OPENROUTER_API_KEY). The conftest guard limits this to exactly one
request (no retries), so running it costs one request from the daily free-model quota.
"""

import os

import pytest

pytestmark = [
    pytest.mark.skipif(os.environ.get("RUN_LIVE_LLM") != "1", reason="set RUN_LIVE_LLM=1 to run"),
    pytest.mark.live_llm,
]


def test_live_prompt_generation(client, openrouter_calls):
    response = client.post("/api/prompts", json={"subject": "A Rainy Day"})
    assert len(openrouter_calls) == 1
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["prompt"]) > 20
    assert len(body["example"].split()) > 30
