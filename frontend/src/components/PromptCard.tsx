import type { GeneratedPrompt } from "@/lib/api";
import { useCardFlip } from "@/lib/useCardFlip";

export type Generation =
  | { status: "loading" }
  // `fallback`: live generation failed and a stored prompt was served instead.
  | ({ status: "ready"; fallback: boolean } & GeneratedPrompt)
  | { status: "error"; message: string };

type Props = {
  /** null until the first subject has been chosen. */
  subject: string | null;
  flipped: boolean;
  generation: Generation;
  onClick: () => void;
};

function hintFor(flipped: boolean, generation: Generation): string {
  if (flipped) return "Tap to flip back to the prompt";
  if (generation.status === "loading") return "Writing your prompt…";
  if (generation.status === "error") return "Tap the card to try again";
  return "Tap the card to see an example";
}

export default function PromptCard({ subject, flipped, generation, onClick }: Props) {
  const ready = generation.status === "ready" ? generation : null;
  // A stored fallback prompt may be for a different subject than the one rolled.
  const shownSubject = ready?.subject ?? subject;
  const { innerRef, shadowRef, frontShadeRef, backShadeRef } = useCardFlip(flipped);

  return (
    <button
      type="button"
      onClick={onClick}
      className="card-scene"
      data-face={flipped ? "back" : "front"}
      aria-busy={generation.status === "loading"}
      aria-describedby="card-hint"
    >
      <span className="card-stage">
        <span ref={shadowRef} className="card-shadow" aria-hidden="true" />
        <span ref={innerRef} className={`card-inner${flipped ? " is-flipped" : ""}`}>
          <span className="card-face card-front" inert={flipped} aria-hidden={flipped}>
            <span ref={frontShadeRef} className="card-shade" aria-hidden="true" />
            <span className="card-label">Subject</span>
            <span className="card-subject" data-testid="subject-text">
              {shownSubject ?? " "}
            </span>
            <span className="card-prompt">
              <span className="card-label">Your prompt</span>
              {generation.status === "loading" && (
                <span className="card-status is-loading" data-testid="card-loading">
                  <span className="card-dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  Writing your prompt…
                </span>
              )}
              {generation.status === "error" && (
                <span className="card-status is-error" role="alert">
                  {generation.message}
                </span>
              )}
              {ready && (
                <span className="card-prompt-text" data-testid="prompt-text">
                  {ready.prompt}
                </span>
              )}
              {ready?.fallback && (
                <span className="card-note">
                  Saved prompt: the live generator is busy right now.
                </span>
              )}
            </span>
          </span>
          <span className="card-face card-back" inert={!flipped} aria-hidden={!flipped}>
            <span ref={backShadeRef} className="card-shade" aria-hidden="true" />
            <span className="card-label">Example response</span>
            <span className="card-subject card-subject--small">{shownSubject}</span>
            <span className="card-example" data-testid="example-text">
              {ready?.example ?? ""}
            </span>
          </span>
        </span>
      </span>
      <span id="card-hint" className="card-hint">
        {hintFor(flipped, generation)}
      </span>
    </button>
  );
}
