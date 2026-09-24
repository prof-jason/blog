# Prompt Generator

A Next.js page for generating writing prompts.

- **Writing prompt card (left):** shows a subject. Click to reveal a prompt; click again to flip the card and see an example response; click once more to flip back.
- **Die (right):** click to roll. After a short animation it picks a new (different) subject and resets the card.

Subjects, prompts, and example responses live in `src/data/prompts.ts`.

## Development

```bash
npm install
npm run dev     # http://localhost:3000
npm test        # Vitest + Testing Library
npm run lint
npm run build
```
