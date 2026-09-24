export type GeneratedPrompt = {
  prompt: string;
  example: string;
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
  const { prompt, example } = await response.json();
  return { prompt, example };
}
