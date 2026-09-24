"use client";

import { useState } from "react";
import { PROMPTS, type WritingPrompt } from "@/data/prompts";
import { nextFace, type CardFace } from "@/lib/cardFace";
import { pickNextIndex, type Rng } from "@/lib/random";
import DiceRoller from "./DiceRoller";
import PromptCard from "./PromptCard";

type Props = {
  prompts?: WritingPrompt[];
  rng?: Rng;
};

export default function PromptStudio({ prompts = PROMPTS, rng = Math.random }: Props) {
  const [index, setIndex] = useState(0);
  const [face, setFace] = useState<CardFace>("subject");
  const [announcement, setAnnouncement] = useState("");

  function handleRoll() {
    const next = pickNextIndex(prompts.length, index, rng);
    setIndex(next);
    setFace("subject");
    setAnnouncement(`New subject: ${prompts[next].subject}`);
  }

  return (
    <div className="studio">
      <section className="studio-card" aria-label="Writing prompt card">
        <PromptCard prompt={prompts[index]} face={face} onAdvance={() => setFace(nextFace)} />
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
