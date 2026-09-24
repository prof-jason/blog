import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchPrompt } from "./api";

function stubFetch(response: Response) {
  const mock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", mock);
  return mock;
}

afterEach(() => vi.unstubAllGlobals());

describe("fetchPrompt", () => {
  it("POSTs the subject as JSON and returns the prompt and example", async () => {
    const mock = stubFetch(
      new Response(JSON.stringify({ subject: "Home", prompt: "P", example: "E" }), { status: 200 }),
    );
    const controller = new AbortController();

    await expect(fetchPrompt("Home", controller.signal)).resolves.toEqual({
      subject: "Home",
      prompt: "P",
      example: "E",
      source: "live",
    });
    expect(mock).toHaveBeenCalledWith("/api/prompts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: "Home" }),
      signal: controller.signal,
    });
  });

  it("passes through a stored fallback for a different subject", async () => {
    stubFetch(
      new Response(JSON.stringify({ subject: "Music", prompt: "P", example: "E", source: "stored" }), {
        status: 200,
      }),
    );
    await expect(fetchPrompt("Home")).resolves.toEqual({
      subject: "Music",
      prompt: "P",
      example: "E",
      source: "stored",
    });
  });

  it("throws the server's error detail", async () => {
    stubFetch(new Response(JSON.stringify({ detail: "Provider down" }), { status: 502 }));
    await expect(fetchPrompt("Home")).rejects.toThrow("Provider down");
  });

  it("throws a friendly fallback when the error body isn't usable", async () => {
    stubFetch(new Response("<html>Bad Gateway</html>", { status: 502 }));
    await expect(fetchPrompt("Home")).rejects.toThrow("Couldn't generate a prompt right now.");
  });
});
