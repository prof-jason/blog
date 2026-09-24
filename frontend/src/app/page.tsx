import PromptStudio from "@/components/PromptStudio";

export default function Home() {
  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">Writing Room</p>
        <h1>Prompt Generator</h1>
        <p className="lede">
          Read your subject and prompt, then tap the card to flip it over for an example response.
          Roll the die whenever you want a new subject.
        </p>
      </header>
      <PromptStudio />
    </main>
  );
}
