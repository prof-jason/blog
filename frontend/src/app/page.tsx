import PromptStudio from "@/components/PromptStudio";

export default function Home() {
  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">Writing Room</p>
        <h1>Prompt Generator</h1>
        <p className="lede">
          Tap the card to reveal a writing prompt, tap again to see an example response. Roll the
          die whenever you want a new subject.
        </p>
      </header>
      <PromptStudio />
    </main>
  );
}
