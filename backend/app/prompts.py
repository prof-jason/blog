import logging
import threading
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints

from app import llm, prompt_store
from app.db import Db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/prompts", tags=["prompts"])

GRADE_LEVEL = "grades 4-6 (ages 9-12)"

# Shared by the single and batch prompts so the two can't drift apart.
_WRITING_GUIDELINES = f"""Your students are in {GRADE_LEVEL}. Write for them:
- prompt: one open-ended writing prompt about the subject, 1-2 short sentences, addressed to the \
student ("you"). Connect it to things a 9-12 year old really experiences or imagines: school, \
friends, family, pets, games, sports, nature, holidays, adventures and make-believe. Use everyday \
words a 4th grader knows. Avoid adult topics (jobs, money, dating, bills) and looking back on \
decades past.
- example: a sample response to that prompt, 60-100 words, written as a strong student in \
{GRADE_LEVEL} would write it: first person, the voice and experiences of a kid that age. Use \
clear, mostly short sentences, a few vivid details and strong verbs, and vocabulary a student \
could realistically use themselves. Plain prose, no title, no preamble.
Keep everything warm, encouraging and appropriate for an elementary or middle school classroom."""

SYSTEM_PROMPT = f"""You are a warm, encouraging creative-writing teacher.
Given a subject, write a writing prompt and an example response.
{_WRITING_GUIDELINES}"""


BATCH_SYSTEM_PROMPT = f"""You are a warm, encouraging creative-writing teacher.
For EACH subject the user lists, write one entry with:
- subject: the subject, copied exactly as given.
- prompt and example, following the guidelines below.
Make each prompt feel distinct: vary the angle, form and opening words across subjects.
{_WRITING_GUIDELINES}"""

# A student is waiting on a card click: give up after this long and serve a stored prompt instead.
LIVE_DEADLINE_SECONDS = 20
# Per-attempt limits for a click, so a request abandoned at the deadline can't keep spending the
# daily quota: at most 1 retry (2 requests), and bad output falls back instead of re-asking.
LIVE_ATTEMPT_TIMEOUT_SECONDS = 15
LIVE_NUM_RETRIES = 1

# Ten prompts and examples are ~2,000 words; give the reply room and time to finish.
BATCH_MAX_TOKENS = 8000
BATCH_TIMEOUT_SECONDS = 180


class PromptRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=80)


# Blank or whitespace-only text is unusable output, so it fails validation (and falls back).
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GeneratedPrompt(BaseModel):
    prompt: NonBlank
    example: NonBlank


class BatchEntry(BaseModel):
    # Defaults keep one incomplete entry from invalidating the whole batch; blanks are dropped.
    subject: str = ""
    prompt: str = ""
    example: str = ""


class PromptBatch(BaseModel):
    prompts: list[BatchEntry] = []


class PromptResponse(GeneratedPrompt):
    subject: str
    # "stored" means live generation failed and a pre-generated prompt was served instead.
    source: Literal["live", "stored"]


def generate_for_subject(subject: str) -> GeneratedPrompt:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Subject: {subject}"},
    ]
    return llm.structured_completion(
        messages,
        GeneratedPrompt,
        parse_attempts=1,
        num_retries=LIVE_NUM_RETRIES,
        timeout=LIVE_ATTEMPT_TIMEOUT_SECONDS,
    )


def generate_live(subject: str) -> GeneratedPrompt:
    """generate_for_subject, but raises LLMError if there's no answer within LIVE_DEADLINE_SECONDS.

    The call runs on a daemon thread so the endpoint can stop waiting; per-attempt limits bound how
    long (and how many requests) an abandoned call can go on for.
    """
    outcome: dict[str, object] = {}
    done = threading.Event()

    def run() -> None:
        try:
            outcome["result"] = generate_for_subject(subject)
        except BaseException as exc:  # handed back to the waiting request below
            outcome["error"] = exc
        finally:
            done.set()

    threading.Thread(target=run, name="live-prompt", daemon=True).start()
    if not done.wait(LIVE_DEADLINE_SECONDS):
        raise llm.LLMError(f"No response from the model within {LIVE_DEADLINE_SECONDS}s")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]


def generate_batch(subjects: list[str]) -> list[prompt_store.StoredPrompt]:
    """Generate prompts for several subjects in ONE request (the free tier limits requests per day).

    Returns the usable entries only: complete, for a subject that was asked for, one per subject.
    Makes exactly one request; the caller decides whether to try again.
    """
    requested = {subject.strip().lower(): subject for subject in subjects}
    listing = "\n".join(f"- {subject}" for subject in subjects)
    messages = [
        {"role": "system", "content": BATCH_SYSTEM_PROMPT},
        {"role": "user", "content": f"Subjects ({len(subjects)}):\n{listing}"},
    ]
    batch = llm.structured_completion(
        messages,
        PromptBatch,
        parse_attempts=1,
        max_tokens=BATCH_MAX_TOKENS,
        timeout=BATCH_TIMEOUT_SECONDS,
    )
    usable: dict[str, prompt_store.StoredPrompt] = {}
    for entry in batch.prompts:
        subject = requested.get(entry.subject.strip().lower())
        prompt, example = entry.prompt.strip(), entry.example.strip()
        if subject and prompt and example and subject not in usable:
            usable[subject] = prompt_store.StoredPrompt(subject=subject, prompt=prompt, example=example)
    return list(usable.values())


@router.get("/stored")
def stored_prompt(db: Db) -> PromptResponse:
    """A random pre-generated prompt, so the page can open on a full card without spending a request."""
    stored = prompt_store.random_prompt(db)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No stored prompts yet")
    return PromptResponse(**stored.model_dump(), source="stored")


@router.post("")
def generate_prompt(body: PromptRequest, db: Db) -> PromptResponse:
    subject = body.subject.strip()
    if not subject:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Subject must not be blank")
    try:
        result = generate_live(subject)
    except llm.LLMError:
        logger.exception("Prompt generation failed for subject %r", subject)
        stored = prompt_store.find_fallback(db, subject)
        if stored is None:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't generate a prompt right now. Please try again.")
        logger.info("Serving stored prompt for %r (requested %r)", stored.subject, subject)
        return PromptResponse(**stored.model_dump(), source="stored")
    return PromptResponse(subject=subject, **result.model_dump(), source="live")
