import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Home from "@/app/page";
import { SUBJECTS } from "@/data/subjects";
import { ROLL_DURATION_MS } from "./DiceRoller";
import PromptStudio from "./PromptStudio";

const FIXTURES = ["Oceans", "Cities", "Forests"];

type Pending = {
  subject: string;
  signal: AbortSignal;
  resolve: (status: number, body: unknown) => Promise<void>;
};

let pending: Pending[];

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  pending = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((_url: string, init: RequestInit) => {
      return new Promise<Response>((resolveFetch) => {
        pending.push({
          subject: JSON.parse(init.body as string).subject,
          signal: init.signal as AbortSignal,
          resolve: async (status, body) => {
            await act(async () => resolveFetch(jsonResponse(status, body)));
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
const subjectOnCard = () => card().querySelector(".card-front .card-subject")?.textContent;

function rollAndSettle() {
  fireEvent.click(die());
  act(() => {
    vi.advanceTimersByTime(ROLL_DURATION_MS);
  });
}

const oceans = { prompt: "Write about tides.", example: "The tide came in slowly." };

describe("PromptStudio", () => {
  it("starts on the subject side without calling the API", () => {
    render(<PromptStudio subjects={FIXTURES} />);
    expect(subjectOnCard()).toBe("Oceans");
    expect(card()).toHaveAttribute("data-face", "subject");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("generates a prompt for the subject on click, then flips to the example and back", async () => {
    render(<PromptStudio subjects={FIXTURES} />);

    fireEvent.click(card());
    expect(pending).toHaveLength(1);
    expect(pending[0].subject).toBe("Oceans");
    expect(fetch).toHaveBeenCalledWith("/api/prompts", expect.objectContaining({ method: "POST" }));
    expect(screen.getByTestId("card-loading")).toBeInTheDocument();
    expect(card()).toHaveAttribute("aria-busy", "true");

    fireEvent.click(card()); // ignored while loading
    expect(pending).toHaveLength(1);

    await pending[0].resolve(200, { subject: "Oceans", ...oceans });
    expect(card()).toHaveAttribute("data-face", "prompt");
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about tides.");
    expect(screen.queryByTestId("card-loading")).not.toBeInTheDocument();

    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "example");
    expect(screen.getByTestId("example-text")).toHaveTextContent("The tide came in slowly.");
    expect(card().querySelector(".card-inner")).toHaveClass("is-flipped");

    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "subject");
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("");
  });

  it("reuses the generated prompt when revisiting the same subject", async () => {
    render(<PromptStudio subjects={FIXTURES} />);
    fireEvent.click(card());
    await pending[0].resolve(200, oceans);
    fireEvent.click(card());
    fireEvent.click(card()); // back to subject

    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "prompt");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("shows the server error and retries on the next click", async () => {
    render(<PromptStudio subjects={FIXTURES} />);
    fireEvent.click(card());
    await pending[0].resolve(502, { detail: "Couldn't generate a prompt right now. Please try again." });

    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't generate a prompt right now.");
    expect(card()).toHaveAttribute("data-face", "subject");
    expect(screen.getByText("Tap the card to try again")).toBeInTheDocument();

    fireEvent.click(card());
    expect(pending).toHaveLength(2);
    await pending[1].resolve(200, oceans);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("Write about tides.");
  });

  it("rolling the die picks a different subject and resets the card", async () => {
    // rng 0.99 → offset 1 of the 2 non-current slots → index 2 ("Forests").
    render(<PromptStudio subjects={FIXTURES} rng={() => 0.99} />);
    fireEvent.click(card());
    await pending[0].resolve(200, oceans);
    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "example");

    rollAndSettle();

    expect(subjectOnCard()).toBe("Forests");
    expect(card()).toHaveAttribute("data-face", "subject");
    expect(screen.getByText("New subject: Forests")).toBeInTheDocument();

    fireEvent.click(card());
    expect(pending[1].subject).toBe("Forests");
  });

  it("aborts and ignores an in-flight request when the die is rolled", async () => {
    render(<PromptStudio subjects={FIXTURES} rng={() => 0} />);
    fireEvent.click(card());
    rollAndSettle();

    expect(pending[0].signal.aborted).toBe(true);
    await pending[0].resolve(200, oceans);

    expect(subjectOnCard()).toBe("Cities");
    expect(card()).toHaveAttribute("data-face", "subject");
    expect(screen.getByTestId("prompt-text")).toHaveTextContent("");
    expect(screen.queryByTestId("card-loading")).not.toBeInTheDocument();
  });

  it("disables the die while rolling and only changes the subject once it settles", () => {
    render(<PromptStudio subjects={FIXTURES} rng={() => 0} />);
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

  it("never repeats the same subject across consecutive rolls with real data", () => {
    render(<PromptStudio />);
    let previous = SUBJECTS[0];
    for (let i = 0; i < 20; i++) {
      rollAndSettle();
      const current = subjectOnCard();
      expect(current).not.toBe(previous);
      expect(SUBJECTS).toContain(current);
      previous = current!;
    }
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
