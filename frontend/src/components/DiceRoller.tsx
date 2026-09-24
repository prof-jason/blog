"use client";

import { useEffect, useRef, useState } from "react";
import { rollDieFace } from "@/lib/random";

export const ROLL_DURATION_MS = 700;
const TICK_MS = 90;

// Pip centres on a 100×100 die, keyed by face value.
const PIPS: Record<number, [number, number][]> = {
  1: [[50, 50]],
  2: [[28, 28], [72, 72]],
  3: [[28, 28], [50, 50], [72, 72]],
  4: [[28, 28], [72, 28], [28, 72], [72, 72]],
  5: [[28, 28], [72, 28], [50, 50], [28, 72], [72, 72]],
  6: [[28, 26], [72, 26], [28, 50], [72, 50], [28, 74], [72, 74]],
};

type Props = {
  onRoll: () => void;
};

export default function DiceRoller({ onRoll }: Props) {
  const [value, setValue] = useState(5);
  const [rolling, setRolling] = useState(false);
  const tick = useRef<ReturnType<typeof setInterval> | null>(null);
  const settle = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (tick.current) clearInterval(tick.current);
      if (settle.current) clearTimeout(settle.current);
    },
    [],
  );

  function roll() {
    if (rolling) return;
    setRolling(true);
    tick.current = setInterval(() => setValue(rollDieFace()), TICK_MS);
    settle.current = setTimeout(() => {
      if (tick.current) clearInterval(tick.current);
      setValue(rollDieFace());
      setRolling(false);
      onRoll();
    }, ROLL_DURATION_MS);
  }

  return (
    <div className="dice-panel">
      <button
        type="button"
        onClick={roll}
        disabled={rolling}
        className={`die${rolling ? " is-rolling" : ""}`}
        aria-label="Roll the die for a new subject"
      >
        <svg viewBox="0 0 100 100" aria-hidden="true" data-value={value}>
          <rect x="4" y="4" width="92" height="92" rx="20" className="die-body" />
          {PIPS[value].map(([cx, cy]) => (
            <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="8.5" className="die-pip" />
          ))}
        </svg>
      </button>
      <p className="dice-caption">{rolling ? "Rolling…" : "Roll for a new subject"}</p>
    </div>
  );
}
