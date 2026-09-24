import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app import llm

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


@router.post("")
def generate_prompt(body: PromptRequest) -> PromptResponse:
    subject = body.subject.strip()
    if not subject:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Subject must not be blank")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Subject: {subject}"},
    ]
    try:
        result = llm.structured_completion(messages, GeneratedPrompt)
    except llm.LLMError:
        logger.exception("Prompt generation failed for subject %r", subject)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't generate a prompt right now. Please try again.")
    return PromptResponse(subject=subject, prompt=result.prompt.strip(), example=result.example.strip())
