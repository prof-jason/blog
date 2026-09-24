import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PROMPTS, type WritingPrompt } from "@/data/prompts";
import Home from "@/app/page";
import { ROLL_DURATION_MS } from "./DiceRoller";
import PromptStudio from "./PromptStudio";

const FIXTURES: WritingPrompt[] = [
  { subject: "Oceans", prompt: "Write about tides.", example: "The tide came in slowly." },
  { subject: "Cities", prompt: "Write about a subway.", example: "The train screeched." },
  { subject: "Forests", prompt: "Write about moss.", example: "Moss covered everything." },
];

const card = () =>
  within(screen.getByRole("region", { name: "Writing prompt card" })).getByRole("button");
const die = () => screen.getByRole("button", { name: /roll the die/i });

function rollAndSettle() {
  fireEvent.click(die());
  act(() => {
    vi.advanceTimersByTime(ROLL_DURATION_MS);
  });
}

describe("PromptStudio", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("starts on the subject side with the prompt and example hidden", () => {
    render(<PromptStudio prompts={FIXTURES} />);
    expect(screen.getAllByText("Oceans").length).toBeGreaterThan(0);
    expect(screen.queryByText("Write about tides.")).not.toBeInTheDocument();
    expect(screen.queryByText("The tide came in slowly.")).not.toBeInTheDocument();
    expect(card()).toHaveAttribute("data-face", "subject");
  });

  it("reveals the prompt, then flips to the example, then back to the subject", () => {
    render(<PromptStudio prompts={FIXTURES} />);

    fireEvent.click(card());
    expect(screen.getByText("Write about tides.")).toBeVisible();
    expect(screen.queryByText("The tide came in slowly.")).not.toBeInTheDocument();
    expect(card()).toHaveAttribute("data-face", "prompt");

    fireEvent.click(card());
    expect(screen.getByText("The tide came in slowly.")).toBeInTheDocument();
    expect(card()).toHaveAttribute("data-face", "example");
    expect(card().querySelector(".card-inner")).toHaveClass("is-flipped");

    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "subject");
    expect(screen.queryByText("Write about tides.")).not.toBeInTheDocument();
  });

  it("rolling the die picks a different subject and resets the card", () => {
    // rng 0.99 → offset 1 of the 2 non-current slots → index 2 ("Forests").
    render(<PromptStudio prompts={FIXTURES} rng={() => 0.99} />);
    fireEvent.click(card());
    fireEvent.click(card());
    expect(card()).toHaveAttribute("data-face", "example");

    rollAndSettle();

    expect(screen.getAllByText("Forests").length).toBeGreaterThan(0);
    expect(screen.queryByText("Oceans")).not.toBeInTheDocument();
    expect(card()).toHaveAttribute("data-face", "subject");
    expect(screen.getByText("New subject: Forests")).toBeInTheDocument();

    fireEvent.click(card());
    expect(screen.getByText("Write about moss.")).toBeInTheDocument();
  });

  it("disables the die while rolling and only changes the subject once it settles", () => {
    render(<PromptStudio prompts={FIXTURES} rng={() => 0} />);
    fireEvent.click(die());

    expect(die()).toBeDisabled();
    expect(screen.getByText("Rolling…")).toBeInTheDocument();
    expect(screen.getAllByText("Oceans").length).toBeGreaterThan(0);

    fireEvent.click(die()); // ignored while rolling
    act(() => {
      vi.advanceTimersByTime(ROLL_DURATION_MS);
    });

    expect(die()).toBeEnabled();
    expect(screen.getAllByText("Cities").length).toBeGreaterThan(0);
  });

  it("never repeats the same subject across consecutive rolls with real data", () => {
    render(<PromptStudio />);
    let previous = PROMPTS[0].subject;
    for (let i = 0; i < 20; i++) {
      rollAndSettle();
      const current = card().querySelector(".card-front .card-subject")?.textContent;
      expect(current).not.toBe(previous);
      expect(PROMPTS.map((p) => p.subject)).toContain(current);
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

describe("prompt data", () => {
  it("has complete, unique entries", () => {
    expect(PROMPTS.length).toBeGreaterThanOrEqual(6);
    expect(new Set(PROMPTS.map((p) => p.subject)).size).toBe(PROMPTS.length);
    for (const p of PROMPTS) {
      expect(p.subject.trim()).not.toBe("");
      expect(p.prompt.trim()).not.toBe("");
      expect(p.example.trim()).not.toBe("");
    }
  });
});
