import { useEffect, useRef } from "react";

export const FLIP_DURATION_MS = 850;
const LIFT_PX = 60;
const TILT_DEG = -3;
const EASING = "cubic-bezier(0.45, 0.05, 0.25, 1)";

/** The card's resting transform; the animation's first and last frames must match it. */
export function restingTransform(flipped: boolean): string {
  return `translateZ(0px) rotateZ(0deg) rotateY(${flipped ? 180 : 0}deg)`;
}

/** Transform keyframes: lift toward the viewer with a slight hand tilt, turn over, settle. */
export function flipKeyframes(toBack: boolean): Keyframe[] {
  const from = toBack ? 0 : 180;
  const to = toBack ? 180 : 0;
  return [
    { transform: restingTransform(!toBack) },
    {
      transform: `translateZ(${LIFT_PX}px) rotateZ(${TILT_DEG}deg) rotateY(${(from + to) / 2}deg)`,
      offset: 0.5,
    },
    { transform: restingTransform(toBack) },
  ];
}

// While the card is in the air its shadow drops and fades, and narrows as the card turns edge-on.
const SHADOW_KEYFRAMES: Keyframe[] = [
  { transform: "translateY(0) scale(1, 1)", opacity: 1 },
  { transform: "translateY(24px) scale(0.25, 0.9)", opacity: 0.5, offset: 0.5 },
  { transform: "translateY(0) scale(1, 1)", opacity: 1 },
];

// Each face darkens as it turns edge-on to the light. Symmetric, so it suits both faces.
const SHADE_KEYFRAMES: Keyframe[] = [
  { opacity: 0 },
  { opacity: 0.45, offset: 0.5 },
  { opacity: 0 },
];

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Plays a physical card-flip whenever `flipped` changes, and returns the refs to attach. The resting
 * state is set by CSS, so without Web Animations support (or with reduced motion) the card simply
 * switches sides. Changing direction mid-flip reverses the running animation from where it is.
 */
export function useCardFlip(flipped: boolean) {
  const inner = useRef<HTMLSpanElement>(null);
  const shadow = useRef<HTMLSpanElement>(null);
  const frontShade = useRef<HTMLSpanElement>(null);
  const backShade = useRef<HTMLSpanElement>(null);
  const previous = useRef(flipped);
  const running = useRef<Animation[]>([]);

  useEffect(() => {
    if (previous.current === flipped) return; // initial render (and StrictMode re-runs)
    previous.current = flipped;

    const card = inner.current;
    if (!card || typeof card.animate !== "function" || prefersReducedMotion()) return;

    const inFlight = running.current.filter((animation) => animation.playState === "running");
    if (inFlight.length > 0) {
      inFlight.forEach((animation) => animation.reverse());
      return;
    }

    const timing: KeyframeAnimationOptions = { duration: FLIP_DURATION_MS, easing: EASING };
    const layers: [HTMLElement | null, Keyframe[]][] = [
      [shadow.current, SHADOW_KEYFRAMES],
      [frontShade.current, SHADE_KEYFRAMES],
      [backShade.current, SHADE_KEYFRAMES],
    ];
    running.current = [
      card.animate(flipKeyframes(flipped), timing),
      ...layers.flatMap(([element, keyframes]) =>
        element ? [element.animate(keyframes, timing)] : [],
      ),
    ];
  }, [flipped]);

  useEffect(() => () => running.current.forEach((animation) => animation.cancel()), []);

  return { innerRef: inner, shadowRef: shadow, frontShadeRef: frontShade, backShadeRef: backShade };
}
