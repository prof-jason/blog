import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app import llm, prompt_store
from app.db import Db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/prompts", tags=["prompts"])

SYSTEM_PROMPT = """You are a warm, encouraging creative-writing teacher.
Given a subject, write:
- prompt: one open-ended writing prompt about that subject, 1-2 sentences, addressed to the student \
("you"), concrete enough to start writing immediately.
- example: a sample response to that prompt, 60-120 words, showing vivid, specific detail a student \
could learn from. Plain prose, no title, no preamble.
Keep everything appropriate for a school classroom."""


class PromptRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=80)


class GeneratedPrompt(BaseModel):
    prompt: str
    example: str


class PromptResponse(GeneratedPrompt):
    subject: str
    # "stored" means live generation failed and a pre-generated prompt was served instead.
    source: Literal["live", "stored"]


def generate_for_subject(subject: str) -> GeneratedPrompt:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Subject: {subject}"},
    ]
    result = llm.structured_completion(messages, GeneratedPrompt)
    return GeneratedPrompt(prompt=result.prompt.strip(), example=result.example.strip())


@router.post("")
def generate_prompt(body: PromptRequest, db: Db) -> PromptResponse:
    subject = body.subject.strip()
    if not subject:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Subject must not be blank")
    try:
        result = generate_for_subject(subject)
    except llm.LLMError:
        logger.exception("Prompt generation failed for subject %r", subject)
        stored = prompt_store.find_fallback(db, subject)
        if stored is None:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't generate a prompt right now. Please try again.")
        logger.info("Serving stored prompt for %r (requested %r)", stored.subject, subject)
        return PromptResponse(**stored.model_dump(), source="stored")
    return PromptResponse(subject=subject, **result.model_dump(), source="live")
