export type Rng = () => number;

/** Returns a die face value from 1 to 6. */
export function rollDieFace(rng: Rng = Math.random): number {
  return Math.floor(rng() * 6) + 1;
}
