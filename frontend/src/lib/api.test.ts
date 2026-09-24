import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchNextPrompt, PromptsNotReadyError } from "./api";

function stubFetch(response: Response) {
  const mock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", mock);
  return mock;
}

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });

afterEach(() => vi.unstubAllGlobals());

describe("fetchNextPrompt", () => {
  it("GETs the next card, excluding the current subject", async () => {
    const mock = stubFetch(json(200, { subject: "Home", prompt: "P", example: "E" }));
    const controller = new AbortController();

    await expect(fetchNextPrompt("A Map & Compass", controller.signal)).resolves.toEqual({
      subject: "Home",
      prompt: "P",
      example: "E",
    });
    expect(mock).toHaveBeenCalledWith("/api/prompts/next?exclude=A%20Map%20%26%20Compass", {
      signal: controller.signal,
    });
  });

  it("asks without an exclusion for the first card", async () => {
    const mock = stubFetch(json(200, { subject: "Home", prompt: "P", example: "E" }));
    await fetchNextPrompt(null);
    expect(mock).toHaveBeenCalledWith("/api/prompts/next", { signal: undefined });
  });

  it("signals 'not ready yet' when the server says when to retry", async () => {
    stubFetch(json(503, { detail: "Prompts are being written." }, { "Retry-After": "3" }));
    const error = await fetchNextPrompt(null).catch((e) => e);
    expect(error).toBeInstanceOf(PromptsNotReadyError);
    expect(error.retryAfterMs).toBe(3000);
  });

  it("treats a 503 without Retry-After as a plain error", async () => {
    stubFetch(json(503, { detail: "No prompts are available right now." }));
    const error = await fetchNextPrompt(null).catch((e) => e);
    expect(error).not.toBeInstanceOf(PromptsNotReadyError);
    expect(error.message).toBe("No prompts are available right now.");
  });

  it("throws a friendly message when the error body isn't usable", async () => {
    stubFetch(new Response("<html>Bad Gateway</html>", { status: 502 }));
    await expect(fetchNextPrompt(null)).rejects.toThrow("Couldn't get a prompt right now.");
  });

  it("rejects a response missing a field instead of showing a blank card", async () => {
    stubFetch(json(200, { subject: "Home", prompt: "P" }));
    await expect(fetchNextPrompt(null)).rejects.toThrow("Couldn't get a prompt right now.");
  });
});
