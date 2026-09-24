from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app import llm, prompt_store
from app.db import Db

router = APIRouter(prefix="/api/prompts", tags=["prompts"])

GRADE_LEVEL = "grades 4-6 (ages 9-12)"

# Grade-level guidelines for every generated prompt; change the audience here.
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

BATCH_SYSTEM_PROMPT = f"""You are a warm, encouraging creative-writing teacher.
For EACH subject the user lists, write one entry with:
- subject: the subject, copied exactly as given.
- prompt and example, following the guidelines below.
Make each prompt feel distinct: vary the angle, form and opening words across subjects.
{_WRITING_GUIDELINES}"""

# Ten prompts and examples are ~2,000 words; give the reply room and time to finish.
BATCH_MAX_TOKENS = 8000
BATCH_TIMEOUT_SECONDS = 180


class BatchEntry(BaseModel):
    # Defaults keep one incomplete entry from invalidating the whole batch; blanks are dropped.
    subject: str = ""
    prompt: str = ""
    example: str = ""


class PromptBatch(BaseModel):
    prompts: list[BatchEntry] = []


class NextPrompt(BaseModel):
    subject: str
    prompt: str
    example: str


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


@router.get("/next")
def next_prompt(request: Request, db: Db, exclude: str | None = None) -> NextPrompt:
    """The next card: a subject (other than `exclude`, the one showing now) with its prompt and example.

    Served from the pre-generated pool, so it's instant and never calls the LLM. Serving may start a
    background refill. If the pool is empty, responds 503, with Retry-After when prompts are on
    the way.
    """
    prompt = prompt_store.take_next(db, exclude)
    pool: prompt_store.PromptPool = request.app.state.prompt_pool
    pool.refill_if_low()
    if prompt is None:
        retry_after = pool.retry_after()
        if retry_after is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "No prompts are available right now. Please try again later."
            )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Prompts are being written. Please wait a moment.",
            headers={"Retry-After": str(retry_after)},
        )
    return NextPrompt(**prompt.model_dump())
