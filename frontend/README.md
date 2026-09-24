# Prompt Generator

A Next.js page for generating writing prompts.

- **Writing prompt card (left):** shows a subject. Click it to generate a prompt for that subject (`POST /api/prompts`, served by the FastAPI backend). Click again to flip the card and see an example response, and click once more to flip back.
- **Die (right):** click to roll. After a short animation it picks a new (different) subject and resets the card.

Subjects live in `src/data/subjects.ts`. In production this app is statically exported and served by the backend. See the root README.

## Development

```bash
npm install
npm run dev     # http://localhost:3000 (proxies /api to the backend on :8000)
npm test        # Vitest + Testing Library
npm run lint
npm run build
```
