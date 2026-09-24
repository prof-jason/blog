"""Real call to OpenRouter (free models router). Opt in with RUN_LIVE_LLM=1 (needs OPENROUTER_API_KEY)."""

import os

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("RUN_LIVE_LLM") != "1", reason="set RUN_LIVE_LLM=1 to run")


def test_live_prompt_generation(client):
    response = client.post("/api/prompts", json={"subject": "A Rainy Day"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["prompt"]) > 20
    assert len(body["example"].split()) > 30
