"""Generic structured-output LLM calls: LiteLLM → OpenRouter (free models router)."""

import logging
import re
from typing import TypeVar

from litellm import completion
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# OpenRouter's router picks a free model at random for each request.
MODEL = "openrouter/openrouter/free"
# Only route to endpoints that honor response_format (structured outputs); prefer Cerebras.
EXTRA_BODY = {"provider": {"order": ["cerebras"], "require_parameters": True}}
TIMEOUT_SECONDS = 60
# Free models are often briefly "temporarily overloaded"; retry with exponential backoff.
NUM_RETRIES = 3
RETRY_STRATEGY = "exponential_backoff_retry"
# Free models format output differently; if a reply can't be parsed, ask again
# (the router will usually pick a different model).
MAX_PARSE_ATTEMPTS = 2

_FENCED = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """The model call failed or returned something that didn't match the schema."""


class UnusableOutputError(LLMError):
    """The call succeeded but the reply was empty or didn't match the schema."""


def extract_json(content: str | None) -> str:
    """The JSON object in a reply, tolerating ```json fences or text around it."""
    if not content:
        raise UnusableOutputError("The model returned an empty response")
    text = content.strip()
    if fenced := _FENCED.match(text):
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else text


def _call(messages: list[dict[str, str]], response_model: type[T], **options) -> T:
    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=response_model,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
            retry_strategy=RETRY_STRATEGY,
            **options,
        )
        content = response.choices[0].message.content
    except Exception as exc:  # litellm raises many provider-specific types
        raise LLMError(str(exc)) from exc
    logger.info("LLM response from %s", getattr(response, "model", "unknown model"))
    try:
        return response_model.model_validate_json(extract_json(content))
    except ValidationError as exc:
        raise UnusableOutputError(f"Response didn't match the schema: {exc}") from exc


def structured_completion(
    messages: list[dict[str, str]],
    response_model: type[T],
    *,
    parse_attempts: int | None = None,
    num_retries: int | None = None,
    max_tokens: int | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> T:
    """Call the model and parse its reply into `response_model`.

    `parse_attempts` (default MAX_PARSE_ATTEMPTS) is how many requests to spend on unusable output;
    callers that manage their own retries pass 1. `num_retries` (default NUM_RETRIES) is how many
    times LiteLLM retries API errors, and `timeout` applies to each attempt.
    """
    attempts = MAX_PARSE_ATTEMPTS if parse_attempts is None else parse_attempts
    options = {
        "timeout": timeout,
        "num_retries": NUM_RETRIES if num_retries is None else num_retries,
    } | ({"max_tokens": max_tokens} if max_tokens else {})
    for attempt in range(1, attempts + 1):
        try:
            return _call(messages, response_model, **options)
        except UnusableOutputError as exc:
            # API errors were already retried by litellm; only bad output gets another try here.
            if attempt == attempts:
                raise
            logger.warning("Unusable LLM output (attempt %d), retrying: %s", attempt, exc)
    raise AssertionError("unreachable")
