import type { GeneratedPrompt } from "@/lib/api";
import type { CardFace } from "@/lib/cardFace";

export type Generation =
  | { status: "idle" }
  | { status: "loading" }
  | ({ status: "ready" } & GeneratedPrompt)
  | { status: "error"; message: string };

type Props = {
  subject: string;
  face: CardFace;
  generation: Generation;
  onAdvance: () => void;
};

function hintFor(face: CardFace, generation: Generation): string {
  if (face === "prompt") return "Tap again to flip for an example";
  if (face === "example") return "Tap to flip back to the subject";
  if (generation.status === "loading") return "Writing your prompt…";
  if (generation.status === "error") return "Tap the card to try again";
  return "Tap the card to reveal your prompt";
}

export default function PromptCard({ subject, face, generation, onAdvance }: Props) {
  const flipped = face === "example";
  const ready = generation.status === "ready" ? generation : null;
  const promptShown = face !== "subject" && ready !== null;
  // A stored fallback prompt may be for a different subject than the one rolled.
  const shownSubject = ready?.subject ?? subject;

  return (
    <button
      type="button"
      onClick={onAdvance}
      className="card-scene"
      data-face={face}
      aria-busy={generation.status === "loading"}
      aria-describedby="card-hint"
    >
      <span className={`card-inner${flipped ? " is-flipped" : ""}`}>
        <span className="card-face card-front" inert={flipped} aria-hidden={flipped}>
          <span className="card-label">Subject</span>
          <span className="card-subject">{shownSubject}</span>
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
          {generation.status === "error" && face === "subject" && (
            <span className="card-status is-error" role="alert">
              {generation.message}
            </span>
          )}
          <span className={`card-prompt${promptShown ? " is-shown" : ""}`} aria-hidden={!promptShown}>
            <span className="card-label">Your prompt</span>
            <span className="card-prompt-text" data-testid="prompt-text">
              {promptShown ? ready.prompt : ""}
            </span>
            {promptShown && ready.source === "stored" && (
              <span className="card-note">Saved prompt: the live generator is busy right now.</span>
            )}
          </span>
        </span>
        <span className="card-face card-back" inert={!flipped} aria-hidden={!flipped}>
          <span className="card-label">Example response</span>
          <span className="card-subject card-subject--small">{shownSubject}</span>
          <span className="card-example" data-testid="example-text">
            {flipped && ready ? ready.example : ""}
          </span>
        </span>
      </span>
      <span id="card-hint" className="card-hint">
        {hintFor(face, generation)}
      </span>
    </button>
  );
}
