import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Home from "@/app/page";
import { SUBJECTS } from "@/data/subjects";
import { ROLL_DURATION_MS } from "./DiceRoller";
import PromptStudio from "./PromptStudio";

const FIXTURES = ["Oceans", "Cities", "Forests"];

type Pending = {
  url: string;
  method: string;
  subject?: string;
  signal: AbortSignal;
  respond: (status: number, body: unknown) => Promise<void>;
};

let pending: Pending[];

beforeEach(() => {
  vi.useFakeTimers();
  pending = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init: RequestInit = {}) => {
      return new Promise<Response>((resolveFetch) => {
        pending.push({
          url,
          method: init.method ?? "GET",
          subject: init.body ? JSON.parse(init.body as string).subject : undefined,
          signal: init.signal as AbortSignal,
          respond: async (status, body) => {
            await act(async () =>
              resolveFetch(
                new Response(JSON.stringify(body), {
                  status,
                  headers: { "Content-Type": "application/json" },
                }),
              ),
            );
          },
        });
      });
    }),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const card = () =>
  within(screen.getByRole("region", { name: "Writing prompt card" })).getByRole("button");
const die = () => screen.getByRole("button", { name: /roll the die/i });
const subjectOnCard = () => screen.getByTestId("subject-text").textContent;
const posts = () => pending.filter((p) => p.method === "POST");
const lastPost = () => posts().at(-1)!;

const tides = { prompt: "Write about tides.", example: "The tide came in slowly." };
const subway = { prompt: "Write about a subway.", example: "The train screeched." };
const moss = { prompt: "Write about moss.", example: "Moss covered everything." };

/** Renders and settles the opening card from a stored prompt (or from live generation if `null`). */
async function open(stored: { subject: string; prompt: string; example: string } | null, rng?: () => number) {
  render(<PromptStudio subjects={FIXTURES} rng={rng} />);
  expect(pending[0].url).toBe("/api/prompts/stored");
  if (stored) {
    await pending[0].respond(200, { ...stored, source: "stored" });
  } else {
    await pending[0].respond(404, { detail: "No stored prompts yet" });
  }
}

function roll() {
  fireEvent.click(die());
  act(() => {
    vi.advanceTimersByTime(ROLL_DURATION_MS);
  });
}

describe("opening card", () => {
  it("shows a stored subject and prompt immediately, without generating one", async () => {
    await open({ subject: "Cities", ...subway });

    expect(subjectOnCard()).toBe("Cities");
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about a subway.");
    expect(card()).toHaveAttribute("data-face", "front");
    expect(posts()).toHaveLength(0);
    expect(screen.queryByText(/saved prompt/i)).not.toBeInTheDocument(); // not a fallback
    expect(screen.getByText("Tap the card to see an example")).toBeInTheDocument();
  });

  it("generates a prompt live when nothing is stored yet", async () => {
    await open(null, () => 0.99); // any-index pick → "Forests"

    expect(lastPost().subject).toBe("Forests");
    expect(subjectOnCard()).toBe("Forests");
    expect(screen.getByTestId("card-loading")).toBeInTheDocument();
    expect(card()).toHaveAttribute("aria-busy", "true");

    await lastPost().respond(200, { subject: "Forests", ...moss, source: "live" });
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about moss.");
    expect(screen.queryByTestId("card-loading")).not.toBeInTheDocument();
  });
});

describe("two steps: prompt on the front, example on the back", () => {
  it("flips to the example on click and back to the prompt on the next click", async () => {
    await open({ subject: "Oceans", ...tides });

    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "back");
    expect(card().querySelector(".card-inner")).toHaveClass("is-flipped");
    expect(screen.getByTestId("example-text")).toHaveTextContent("The tide came in slowly.");
    expect(screen.getByText("Tap to flip back to the prompt")).toBeInTheDocument();

    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "front");
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about tides.");

    expect(posts()).toHaveLength(0); // flipping never costs a request
  });

  it("ignores card clicks while a prompt is loading", async () => {
    await open(null, () => 0);
    fireEvent.click(card());
    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "front");
    expect(posts()).toHaveLength(1);
  });
});

describe("rolling the die", () => {
  it("shows a new subject with its prompt, back on the front of the card", async () => {
    // rng 0.99 → offset 1 of the 2 non-current slots → index 2 ("Forests").
    await open({ subject: "Oceans", ...tides }, () => 0.99);
    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "back");

    roll();

    expect(subjectOnCard()).toBe("Forests");
    expect(card()).toHaveAttribute("data-face", "front");
    expect(screen.getByTestId("card-loading")).toBeInTheDocument();
    expect(lastPost().subject).toBe("Forests");
    expect(screen.getByText("New subject: Forests")).toBeInTheDocument();

    await lastPost().respond(200, { subject: "Forests", ...moss, source: "live" });
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about moss.");

    fireEvent.click(card());
    expect(screen.getByTestId("example-text")).toHaveTextContent("Moss covered everything.");
  });

  it("abandons a prompt that is still loading when rolled again", async () => {
    await open({ subject: "Oceans", ...tides }, () => 0);
    roll(); // → Cities
    const first = lastPost();
    roll(); // → Oceans

    expect(first.signal.aborted).toBe(true);
    await first.respond(200, { subject: "Cities", ...subway, source: "live" });
    expect(subjectOnCard()).toBe("Oceans"); // the stale answer is ignored
    expect(screen.getByTestId("card-loading")).toBeInTheDocument();
  });

  it("disables the die while it rolls and only changes the subject once it settles", async () => {
    await open({ subject: "Oceans", ...tides }, () => 0);
    fireEvent.click(die());

    expect(die()).toBeDisabled();
    expect(screen.getByText("Rolling…")).toBeInTheDocument();
    expect(subjectOnCard()).toBe("Oceans");

    act(() => {
      vi.advanceTimersByTime(ROLL_DURATION_MS);
    });

    expect(die()).toBeEnabled();
    expect(subjectOnCard()).toBe("Cities");
  });

  it("never repeats the same subject across consecutive rolls with real data", async () => {
    render(<PromptStudio />);
    await pending[0].respond(200, { subject: SUBJECTS[0], ...tides, source: "stored" });
    let previous = SUBJECTS[0];
    for (let i = 0; i < 20; i++) {
      roll();
      const current = subjectOnCard()!;
      expect(current).not.toBe(previous);
      expect(SUBJECTS).toContain(current);
      previous = current;
    }
  });
});

describe("errors and fallbacks", () => {
  it("shows the error and retries the same subject when the card is clicked", async () => {
    await open({ subject: "Oceans", ...tides }, () => 0);
    roll(); // → Cities
    await lastPost().respond(502, { detail: "Couldn't generate a prompt right now. Please try again." });

    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't generate a prompt right now.");
    expect(screen.getByText("Tap the card to try again")).toBeInTheDocument();
    expect(card()).toHaveAttribute("data-face", "front");

    fireEvent.click(card());
    expect(posts()).toHaveLength(2);
    expect(lastPost().subject).toBe("Cities");
    await lastPost().respond(200, { subject: "Cities", ...subway, source: "live" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about a subway.");
  });

  it("labels a stored fallback and switches to its subject", async () => {
    await open({ subject: "Oceans", ...tides }, () => 0);
    roll(); // asks for Cities...
    await lastPost().respond(200, { subject: "Forests", ...moss, source: "stored" }); // ...gets Forests

    expect(subjectOnCard()).toBe("Forests");
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about moss.");
    expect(screen.getByText(/saved prompt/i)).toBeInTheDocument();
    fireEvent.click(card());
    expect(card().querySelector(".card-back .card-subject")).toHaveTextContent("Forests");

    roll(); // from Forests (index 2), rng 0 → Oceans; never Forests again
    expect(subjectOnCard()).toBe("Oceans");
  });

  it("does not label live prompts as saved", async () => {
    await open({ subject: "Oceans", ...tides }, () => 0);
    roll();
    await lastPost().respond(200, { subject: "Cities", ...subway, source: "live" });
    expect(screen.queryByText(/saved prompt/i)).not.toBeInTheDocument();
  });
});

describe("Home page", () => {
  it("renders the heading, the card, and the die", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1, name: "Prompt Generator" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Writing prompt card" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Subject randomizer" })).toBeInTheDocument();
  });
});

describe("subject data", () => {
  it("has unique, non-empty subjects that fit the API limit", () => {
    expect(SUBJECTS.length).toBeGreaterThanOrEqual(6);
    expect(new Set(SUBJECTS).size).toBe(SUBJECTS.length);
    for (const subject of SUBJECTS) {
      expect(subject.trim()).not.toBe("");
      expect(subject.length).toBeLessThanOrEqual(80);
    }
  });
});
