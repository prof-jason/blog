"use client";

import { useEffect, useRef, useState } from "react";
import { fetchNextPrompt, PromptsNotReadyError } from "@/lib/api";
import DiceRoller from "./DiceRoller";
import PromptCard, { type Generation } from "./PromptCard";

/** Stop waiting for the server to finish writing prompts after this long, and show an error. */
export const MAX_WAIT_MS = 120_000;

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}

/**
 * Two steps: the card's front shows a subject with its prompt, and a click flips it to the example
 * (and back). Rolling the die brings the next card from the server's prompt pool.
 */
export default function PromptStudio() {
  const [flipped, setFlipped] = useState(false);
  const [generation, setGeneration] = useState<Generation>({ status: "loading" });
  const [announcement, setAnnouncement] = useState("");
  const request = useRef<AbortController | null>(null);
  // Read when a roll settles, so it's never a stale copy from when the die was clicked.
  const currentSubject = useRef<string | null>(null);

  /** Cancels whatever is in flight; the returned controller owns the next request. */
  function begin(): AbortController {
    request.current?.abort();
    request.current = new AbortController();
    return request.current;
  }

  /** Shows the next card. Keeps the current card until it arrives (normally instantly). */
  async function loadNext(controller: AbortController) {
    let waited = 0;
    for (;;) {
      try {
        const card = await fetchNextPrompt(currentSubject.current, controller.signal);
        if (controller.signal.aborted) return;
        currentSubject.current = card.subject;
        setGeneration({ status: "ready", ...card });
        setAnnouncement(`${card.subject}. ${card.prompt}`);
        return;
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error instanceof PromptsNotReadyError && waited < MAX_WAIT_MS) {
          setGeneration({ status: "loading" });
          await sleep(error.retryAfterMs, controller.signal);
          waited += error.retryAfterMs;
          continue;
        }
        const message = error instanceof Error ? error.message : "Something went wrong.";
        setGeneration({ status: "error", message });
        return;
      }
    }
  }

  useEffect(() => {
    const controller = begin();
    void loadNext(controller);
    return () => controller.abort();
  }, []);

  function handleCardClick() {
    if (generation.status === "ready") {
      setFlipped((side) => !side);
    } else if (generation.status === "error") {
      setGeneration({ status: "loading" });
      void loadNext(begin());
    }
  }

  function handleRoll() {
    setFlipped(false);
    void loadNext(begin());
  }

  return (
    <div className="studio">
      <section className="studio-card" aria-label="Writing prompt card">
        <PromptCard flipped={flipped} generation={generation} onClick={handleCardClick} />
      </section>
      <section className="studio-dice" aria-label="Subject randomizer">
        <DiceRoller onRoll={handleRoll} />
      </section>
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </div>
  );
}
