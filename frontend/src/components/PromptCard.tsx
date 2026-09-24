import type { WritingPrompt } from "@/data/prompts";
import type { CardFace } from "@/lib/cardFace";

const HINTS: Record<CardFace, string> = {
  subject: "Tap the card to reveal your prompt",
  prompt: "Tap again to flip for an example",
  example: "Tap to flip back to the subject",
};

type Props = {
  prompt: WritingPrompt;
  face: CardFace;
  onAdvance: () => void;
};

export default function PromptCard({ prompt, face, onAdvance }: Props) {
  const flipped = face === "example";
  const promptShown = face !== "subject";

  return (
    <button
      type="button"
      onClick={onAdvance}
      className="card-scene"
      data-face={face}
      aria-describedby="card-hint"
    >
      <span className={`card-inner${flipped ? " is-flipped" : ""}`}>
        <span className="card-face card-front" inert={flipped} aria-hidden={flipped}>
          <span className="card-label">Subject</span>
          <span className="card-subject">{prompt.subject}</span>
          <span className={`card-prompt${promptShown ? " is-shown" : ""}`} aria-hidden={!promptShown}>
            <span className="card-label">Your prompt</span>
            <span className="card-prompt-text" data-testid="prompt-text">
              {promptShown ? prompt.prompt : ""}
            </span>
          </span>
        </span>
        <span className="card-face card-back" inert={!flipped} aria-hidden={!flipped}>
          <span className="card-label">Example response</span>
          <span className="card-subject card-subject--small">{prompt.subject}</span>
          <span className="card-example" data-testid="example-text">
            {flipped ? prompt.example : ""}
          </span>
        </span>
      </span>
      <span id="card-hint" className="card-hint">
        {HINTS[face]}
      </span>
    </button>
  );
}
