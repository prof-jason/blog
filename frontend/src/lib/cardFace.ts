export type CardFace = "subject" | "prompt" | "example";

const ORDER: CardFace[] = ["subject", "prompt", "example"];

/** subject → prompt → example (card flipped) → back to subject. */
export function nextFace(face: CardFace): CardFace {
  return ORDER[(ORDER.indexOf(face) + 1) % ORDER.length];
}
