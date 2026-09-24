import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FLIP_DURATION_MS, flipKeyframes, restingTransform } from "@/lib/useCardFlip";
import PromptCard, { type Generation } from "./PromptCard";

type FakeAnimation = {
  target: Element;
  keyframes: Keyframe[];
  options: KeyframeAnimationOptions;
  playState: AnimationPlayState;
  reverse: ReturnType<typeof vi.fn>;
  cancel: ReturnType<typeof vi.fn>;
};

let animations: FakeAnimation[];

beforeEach(() => {
  animations = [];
  Element.prototype.animate = vi.fn(function (this: Element, keyframes, options) {
    const animation: FakeAnimation = {
      target: this,
      keyframes: keyframes as Keyframe[],
      options: options as KeyframeAnimationOptions,
      playState: "running",
      reverse: vi.fn(),
      cancel: vi.fn(),
    };
    animations.push(animation);
    return animation as unknown as Animation;
  });
});

afterEach(() => {
  // jsdom has no Web Animations API; remove the stub so other suites see the real environment.
  delete (Element.prototype as Partial<Element>).animate;
  vi.unstubAllGlobals();
});

const ready: Generation = {
  status: "ready",
  subject: "Oceans",
  prompt: "Write about tides.",
  example: "The tide came in slowly.",
};

function renderCard(flipped: boolean) {
  const view = render(
    <PromptCard flipped={flipped} generation={ready} onClick={() => {}} />,
  );
  return {
    ...view,
    setFlipped: (next: boolean) =>
      view.rerender(
        <PromptCard flipped={next} generation={ready} onClick={() => {}} />,
      ),
  };
}

const innerAnimation = () => animations.find((a) => a.target.classList.contains("card-inner"))!;
const finishAll = () => animations.forEach((a) => (a.playState = "finished"));

describe("card flip animation", () => {
  it("does not animate on first render, even when mounted flipped", () => {
    renderCard(false);
    renderCard(true);
    expect(animations).toHaveLength(0);
  });

  it("flips to the back with a lift, a floor shadow and edge shading", () => {
    const { setFlipped, container } = renderCard(false);
    setFlipped(true);

    const targets = animations.map((a) => a.target);
    expect(targets).toEqual([
      container.querySelector(".card-inner"),
      container.querySelector(".card-shadow"),
      container.querySelector(".card-front .card-shade"),
      container.querySelector(".card-back .card-shade"),
    ]);
    for (const animation of animations) {
      expect(animation.options.duration).toBe(FLIP_DURATION_MS);
    }

    const keyframes = innerAnimation().keyframes;
    expect(keyframes[0].transform).toBe(restingTransform(false));
    expect(keyframes[1].transform).toContain("rotateY(90deg)");
    expect(keyframes[1].transform).toMatch(/translateZ\([1-9]\d*px\)/); // lifted toward the viewer
    expect(keyframes.at(-1)!.transform).toBe(restingTransform(true));
    expect(container.querySelector(".card-inner")).toHaveClass("is-flipped");
  });

  it("flips back to the front in the opposite direction", () => {
    const { setFlipped } = renderCard(false);
    setFlipped(true);
    finishAll();
    setFlipped(false);

    expect(animations).toHaveLength(8);
    const back = animations[4].keyframes;
    expect(back[0].transform).toBe(restingTransform(true));
    expect(back.at(-1)!.transform).toBe(restingTransform(false));
  });

  it("reverses a flip that is still running instead of jumping", () => {
    const { setFlipped } = renderCard(false);
    setFlipped(true);
    setFlipped(false); // e.g. clicked again, or the die was rolled, mid-flip

    expect(animations).toHaveLength(4);
    for (const animation of animations) {
      expect(animation.reverse).toHaveBeenCalledTimes(1);
    }
  });

  it("skips the animation for users who prefer reduced motion", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduce") }));
    const { setFlipped, container } = renderCard(false);
    setFlipped(true);

    expect(animations).toHaveLength(0);
    expect(container.querySelector(".card-inner")).toHaveClass("is-flipped");
  });

  it("still switches sides when the Web Animations API is unavailable", () => {
    delete (Element.prototype as Partial<Element>).animate;
    const { setFlipped, container } = renderCard(false);
    setFlipped(true);
    expect(container.querySelector(".card-inner")).toHaveClass("is-flipped");
  });

  it("cancels running animations on unmount", () => {
    const { setFlipped, unmount } = renderCard(false);
    setFlipped(true);
    unmount();
    for (const animation of animations) {
      expect(animation.cancel).toHaveBeenCalled();
    }
  });

  it("keeps the example on the back while it flips away, hidden from assistive tech", () => {
    const { setFlipped, container } = renderCard(true);
    setFlipped(false);

    const back = container.querySelector(".card-back")!;
    expect(screen.getByTestId("example-text")).toHaveTextContent("The tide came in slowly.");
    expect(back).toHaveAttribute("aria-hidden", "true");
    expect(back).toHaveAttribute("inert");
  });
});

describe("flipKeyframes", () => {
  it("starts and ends at the resting transforms in both directions", () => {
    expect(flipKeyframes(true)[0].transform).toBe(restingTransform(false));
    expect(flipKeyframes(true).at(-1)!.transform).toBe(restingTransform(true));
    expect(flipKeyframes(false)[0].transform).toBe(restingTransform(true));
    expect(flipKeyframes(false).at(-1)!.transform).toBe(restingTransform(false));
  });
});

describe("card CSS", () => {
  it("rests at exactly the transforms the flip animation starts and ends on", () => {
    const css = readFileSync(join(process.cwd(), "src/app/globals.css"), "utf8");
    const rule = (selector: string) =>
      css.match(new RegExp(`${selector.replaceAll(".", "\\.")} \\{[^}]*transform: ([^;]+);`))?.[1];
    expect(rule(".card-inner")).toBe(restingTransform(false));
    expect(rule(".card-inner.is-flipped")).toBe(restingTransform(true));
  });
});
