export type Rng = () => number;

/**
 * Picks a random index in [0, length) that differs from `current` when possible.
 * A `current` outside the range (e.g. -1 for "none yet") allows any index.
 */
export function pickNextIndex(length: number, current: number, rng: Rng = Math.random): number {
  if (length <= 1) return 0;
  if (current < 0 || current >= length) return Math.floor(rng() * length);
  // Choose among the other length - 1 slots, then skip over `current`.
  const offset = Math.floor(rng() * (length - 1));
  return offset >= current ? offset + 1 : offset;
}

/** Returns a die face value from 1 to 6. */
export function rollDieFace(rng: Rng = Math.random): number {
  return Math.floor(rng() * 6) + 1;
}
