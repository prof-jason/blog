"use client";

import { useEffect, useRef, useState } from "react";
import { SUBJECTS } from "@/data/subjects";
import { fetchPrompt } from "@/lib/api";
import { nextFace, type CardFace } from "@/lib/cardFace";
import { pickNextIndex, type Rng } from "@/lib/random";
import DiceRoller from "./DiceRoller";
import PromptCard, { type Generation } from "./PromptCard";

type Props = {
  subjects?: string[];
  rng?: Rng;
};

export default function PromptStudio({ subjects = SUBJECTS, rng = Math.random }: Props) {
  const [index, setIndex] = useState(0);
  const [face, setFace] = useState<CardFace>("subject");
  const [generation, setGeneration] = useState<Generation>({ status: "idle" });
  const [announcement, setAnnouncement] = useState("");
  const request = useRef<AbortController | null>(null);

  useEffect(() => () => request.current?.abort(), []);

  async function generate(subject: string) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setGeneration({ status: "loading" });
    try {
      const result = await fetchPrompt(subject, controller.signal);
      if (controller.signal.aborted) return;
      const served = subjects.indexOf(result.subject);
      if (served !== -1) setIndex(served); // keep the die from re-rolling a fallback's subject
      setGeneration({ status: "ready", ...result });
      setFace("prompt");
      setAnnouncement(`Prompt: ${result.prompt}`);
    } catch (error) {
      if (controller.signal.aborted) return;
      const message = error instanceof Error ? error.message : "Something went wrong.";
      setGeneration({ status: "error", message });
    }
  }

  function handleCardClick() {
    if (face !== "subject") {
      setFace(nextFace);
    } else if (generation.status === "ready") {
      setFace("prompt");
    } else if (generation.status !== "loading") {
      void generate(subjects[index]);
    }
  }

  function handleRoll() {
    request.current?.abort();
    const next = pickNextIndex(subjects.length, index, rng);
    setIndex(next);
    setFace("subject");
    setGeneration({ status: "idle" });
    setAnnouncement(`New subject: ${subjects[next]}`);
  }

  return (
    <div className="studio">
      <section className="studio-card" aria-label="Writing prompt card">
        <PromptCard
          subject={subjects[index]}
          face={face}
          generation={generation}
          onAdvance={handleCardClick}
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
