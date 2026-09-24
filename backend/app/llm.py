"""Generic structured-output LLM calls: LiteLLM → OpenRouter → Cerebras."""

from typing import TypeVar

from litellm import completion
from pydantic import BaseModel

MODEL = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}
TIMEOUT_SECONDS = 60
# The free tier is often briefly "temporarily overloaded"; retry with exponential backoff.
NUM_RETRIES = 3
RETRY_STRATEGY = "exponential_backoff_retry"

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """The model call failed or returned something that didn't match the schema."""


def structured_completion(messages: list[dict[str, str]], response_model: type[T]) -> T:
    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=response_model,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
            timeout=TIMEOUT_SECONDS,
            num_retries=NUM_RETRIES,
            retry_strategy=RETRY_STRATEGY,
        )
        content = response.choices[0].message.content
        return response_model.model_validate_json(content)
    except Exception as exc:  # litellm raises many provider-specific types
        raise LLMError(str(exc)) from exc
