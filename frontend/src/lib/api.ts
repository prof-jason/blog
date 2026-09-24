export type GeneratedPrompt = {
  /** May differ from the requested subject when the server falls back to a stored prompt. */
  subject: string;
  prompt: string;
  example: string;
  /** "stored" = live generation failed and a prompt pre-generated at startup was served. */
  source: "live" | "stored";
};

const FALLBACK_ERROR = "Couldn't generate a prompt right now. Please try again.";

/** Asks the backend (LLM via Cerebras) for a writing prompt and example response. */
export async function fetchPrompt(subject: string, signal?: AbortSignal): Promise<GeneratedPrompt> {
  const response = await fetch("/api/prompts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject }),
    signal,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : FALLBACK_ERROR);
  }
  const body = await response.json();
  return {
    subject: body.subject ?? subject,
    prompt: body.prompt,
    example: body.example,
    source: body.source === "stored" ? "stored" : "live",
  };
}
