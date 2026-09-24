"use client";

import { useEffect, useRef, useState } from "react";
import { SUBJECTS } from "@/data/subjects";
import { fetchPrompt, fetchStoredPrompt } from "@/lib/api";
import { pickNextIndex, type Rng } from "@/lib/random";
import DiceRoller from "./DiceRoller";
import PromptCard, { type Generation } from "./PromptCard";

type Props = {
  subjects?: string[];
  rng?: Rng;
};

/**
 * Two steps: the card's front shows a subject with its prompt, and a click flips it to the example
 * (and back). Rolling the die shows a new subject with its prompt on the front.
 */
export default function PromptStudio({ subjects = SUBJECTS, rng = Math.random }: Props) {
  const [subject, setSubject] = useState<string | null>(null);
  const [flipped, setFlipped] = useState(false);
  const [generation, setGeneration] = useState<Generation>({ status: "loading" });
  const [announcement, setAnnouncement] = useState("");
  const request = useRef<AbortController | null>(null);

  /** Cancels whatever is in flight; the returned controller owns the next request. */
  function begin(): AbortController {
    request.current?.abort();
    request.current = new AbortController();
    return request.current;
  }

  async function showPrompt(next: string, controller: AbortController) {
    setSubject(next);
    setFlipped(false);
    setGeneration({ status: "loading" });
    try {
      const result = await fetchPrompt(next, controller.signal);
      if (controller.signal.aborted) return;
      setSubject(result.subject);
      setGeneration({ status: "ready", ...result, fallback: result.source === "stored" });
      setAnnouncement(`${result.subject}. ${result.prompt}`);
    } catch (error) {
      if (controller.signal.aborted) return;
      const message = error instanceof Error ? error.message : "Something went wrong.";
      setGeneration({ status: "error", message });
    }
  }

  // Open on a full card: a prompt pre-generated at startup costs no request and shows instantly.
  // Only if none are stored yet (the server just started) is one generated live.
  useEffect(() => {
    const controller = begin();
    (async () => {
      const stored = await fetchStoredPrompt(controller.signal);
      if (controller.signal.aborted) return;
      if (stored) {
        setSubject(stored.subject);
        setGeneration({ status: "ready", ...stored, fallback: false });
      } else {
        await showPrompt(subjects[pickNextIndex(subjects.length, -1, rng)], controller);
      }
    })();
    return () => controller.abort();
    // Runs once on mount; begin/showPrompt only touch refs and state setters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleCardClick() {
    if (generation.status === "ready") {
      setFlipped((side) => !side);
    } else if (generation.status === "error" && subject) {
      void showPrompt(subject, begin());
    }
  }

  function handleRoll() {
    const current = subject === null ? -1 : subjects.indexOf(subject);
    const next = subjects[pickNextIndex(subjects.length, current, rng)];
    setAnnouncement(`New subject: ${next}`);
    void showPrompt(next, begin());
  }

  return (
    <div className="studio">
      <section className="studio-card" aria-label="Writing prompt card">
        <PromptCard
          subject={subject}
          flipped={flipped}
          generation={generation}
          onClick={handleCardClick}
        />
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
