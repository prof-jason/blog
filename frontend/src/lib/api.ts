export type CardPrompt = {
  subject: string;
  prompt: string;
  example: string;
};

const FALLBACK_ERROR = "Couldn't get a prompt right now. Please try again.";

/** The server is still writing prompts; ask again after `retryAfterMs`. */
export class PromptsNotReadyError extends Error {
  constructor(
    message: string,
    readonly retryAfterMs: number,
  ) {
    super(message);
    this.name = "PromptsNotReadyError";
  }
}

/**
 * The next card from the server's pre-generated pool: a subject other than `exclude` (the one on
 * the card now) with its prompt and example. Instant, and never waits on the AI.
 */
export async function fetchNextPrompt(exclude: string | null, signal?: AbortSignal): Promise<CardPrompt> {
  const query = exclude ? `?exclude=${encodeURIComponent(exclude)}` : "";
  const response = await fetch(`/api/prompts/next${query}`, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = typeof body?.detail === "string" ? body.detail : FALLBACK_ERROR;
    const retryAfter = Number(response.headers.get("Retry-After"));
    if (response.status === 503 && retryAfter > 0) {
      throw new PromptsNotReadyError(message, retryAfter * 1000);
    }
    throw new Error(message);
  }
  const body = await response.json();
  if (![body?.subject, body?.prompt, body?.example].every((field) => typeof field === "string" && field)) {
    throw new Error(FALLBACK_ERROR);
  }
  return { subject: body.subject, prompt: body.prompt, example: body.example };
}
