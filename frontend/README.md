# Prompt Generator

A Next.js page for generating writing prompts.

- **Writing prompt card (left):** the front shows a subject and its prompt. The page opens on a stored prompt (`GET /api/prompts/stored`), falling back to generating one live if none are stored yet. Click the card to flip it to an example response, and click again to flip back.
- **Die (right):** click to roll. After a short animation it picks a new (different) subject, turns the card to its front, and generates that subject's prompt (`POST /api/prompts`).

Subjects live in `src/data/subjects.ts`. In production this app is statically exported and served by the backend. See the root README.

## Development

```bash
npm install
npm run dev     # http://localhost:3000 (proxies /api to the backend on :8000)
npm test        # Vitest + Testing Library
npm run lint
npm run build
```
