import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Home from "@/app/page";
import { ROLL_DURATION_MS } from "./DiceRoller";
import PromptStudio, { MAX_WAIT_MS } from "./PromptStudio";

type Pending = {
  url: string;
  signal: AbortSignal;
  respond: (status: number, body: unknown, headers?: Record<string, string>) => Promise<void>;
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
          signal: init.signal as AbortSignal,
          respond: async (status, body, headers = {}) => {
            await act(async () =>
              resolveFetch(
                new Response(JSON.stringify(body), {
                  status,
                  headers: { "Content-Type": "application/json", ...headers },
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
const subjectOnCard = () => screen.getByTestId("subject-text").textContent?.trim();
const last = () => pending.at(-1)!;

const oceans = { subject: "Oceans", prompt: "Write about tides.", example: "The tide came in slowly." };
const cities = { subject: "Cities", prompt: "Write about a subway.", example: "The train screeched." };
const forests = { subject: "Forests", prompt: "Write about moss.", example: "Moss covered everything." };

async function open(first = oceans) {
  render(<PromptStudio />);
  expect(last().url).toBe("/api/prompts/next");
  await last().respond(200, first);
}

function settleRoll() {
  act(() => {
    vi.advanceTimersByTime(ROLL_DURATION_MS);
  });
}

function roll() {
  fireEvent.click(die());
  settleRoll();
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("opening card", () => {
  it("shows a subject and its prompt from the pool", async () => {
    render(<PromptStudio />);
    expect(screen.getByTestId("card-loading")).toBeInTheDocument();
    expect(card()).toHaveAttribute("aria-busy", "true");

    await last().respond(200, oceans);

    expect(subjectOnCard()).toBe("Oceans");
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about tides.");
    expect(card()).toHaveAttribute("data-face", "front");
    expect(screen.getByText("Tap the card to see an example")).toBeInTheDocument();
  });
});

describe("two steps: prompt on the front, example on the back", () => {
  it("flips to the example and back without any requests", async () => {
    await open();

    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "back");
    expect(card().querySelector(".card-inner")).toHaveClass("is-flipped");
    expect(screen.getByTestId("example-text")).toHaveTextContent("The tide came in slowly.");

    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "front");
    expect(pending).toHaveLength(1);
  });

  it("ignores card clicks while the first card is loading", () => {
    render(<PromptStudio />);
    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "front");
    expect(pending).toHaveLength(1);
  });
});

describe("rolling the die", () => {
  it("brings the next card, asking for a different subject, back on the front", async () => {
    await open();
    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "back");

    roll();

    expect(card()).toHaveAttribute("data-face", "front");
    expect(last().url).toBe("/api/prompts/next?exclude=Oceans");
    // The current card stays up until the next one arrives: no loading flash.
    expect(subjectOnCard()).toBe("Oceans");
    expect(screen.queryByTestId("card-loading")).not.toBeInTheDocument();

    await last().respond(200, cities);
    expect(subjectOnCard()).toBe("Cities");
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about a subway.");
    fireEvent.click(card());
    expect(screen.getByTestId("example-text")).toHaveTextContent("The train screeched.");
  });

  it("excludes the subject showing when the roll settles, not when it started", async () => {
    render(<PromptStudio />);
    const opening = last();
    fireEvent.click(die()); // clicked before the first card arrived...
    await opening.respond(200, oceans); // ...which arrives mid-roll
    settleRoll();
    expect(last().url).toBe("/api/prompts/next?exclude=Oceans");
  });

  it("ignores a stale answer when rolled again before it arrives", async () => {
    await open();
    roll();
    const first = last();
    roll();

    expect(first.signal.aborted).toBe(true);
    await first.respond(200, cities);
    expect(subjectOnCard()).toBe("Oceans");

    await last().respond(200, forests);
    expect(subjectOnCard()).toBe("Forests");
  });

  it("disables the die while it rolls and only asks once it settles", async () => {
    await open();
    fireEvent.click(die());

    expect(die()).toBeDisabled();
    expect(screen.getByText("Rolling…")).toBeInTheDocument();
    expect(pending).toHaveLength(1);

    settleRoll();
    expect(die()).toBeEnabled();
    expect(pending).toHaveLength(2);
  });
});

describe("when prompts aren't ready or something fails", () => {
  it("waits and retries while the server is still writing prompts", async () => {
    render(<PromptStudio />);
    await last().respond(503, { detail: "Prompts are being written." }, { "Retry-After": "3" });

    expect(screen.getByTestId("card-loading")).toBeInTheDocument();
    expect(pending).toHaveLength(1);

    await advance(3000);
    expect(pending).toHaveLength(2);
    await last().respond(200, oceans);
    expect(subjectOnCard()).toBe("Oceans");
  });

  it("gives up waiting after MAX_WAIT_MS and lets a click try again", async () => {
    render(<PromptStudio />);
    for (let waited = 0; waited <= MAX_WAIT_MS; waited += 10_000) {
      await last().respond(503, { detail: "Prompts are being written." }, { "Retry-After": "10" });
      await advance(10_000);
    }

    expect(screen.getByRole("alert")).toHaveTextContent("Prompts are being written.");
    expect(screen.getByText("Tap the card to try again")).toBeInTheDocument();
    const requests = pending.length;

    fireEvent.click(card());
    expect(pending).toHaveLength(requests + 1);
    await last().respond(200, oceans);
    expect(subjectOnCard()).toBe("Oceans");
  });

  it("shows an error straight away when no prompts are coming, and retries on click", async () => {
    render(<PromptStudio />);
    await last().respond(503, { detail: "No prompts are available right now. Please try again later." });

    expect(screen.getByRole("alert")).toHaveTextContent("No prompts are available right now.");
    expect(card()).toHaveAttribute("data-face", "front");

    fireEvent.click(card());
    expect(screen.getByTestId("card-loading")).toBeInTheDocument();
    await last().respond(200, cities);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(subjectOnCard()).toBe("Cities");
  });

  it("shows server errors and retries on click", async () => {
    await open();
    roll();
    await last().respond(500, { detail: "Internal Server Error" });

    expect(screen.getByRole("alert")).toHaveTextContent("Internal Server Error");
    fireEvent.click(card());
    expect(last().url).toBe("/api/prompts/next?exclude=Oceans");
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
