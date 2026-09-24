# Prompt Generator

A Next.js page for generating writing prompts.

- **Writing prompt card (left):** the front shows a subject and its prompt, from the server's prompt pool (`GET /api/prompts/next`). Click the card to flip it to an example response, and click again to flip back.
- **Die (right):** click to roll. After a short animation the card turns to its front with the next card from the pool, for a different subject (`GET /api/prompts/next?exclude=<current subject>`).

The server picks subjects (`backend/subjects.json`). In production this app is statically exported and served by the backend. See the root README.

## Development

```bash
npm install
npm run dev     # http://localhost:3000 (proxies /api to the backend on :8000)
npm test        # Vitest + Testing Library
npm run lint
npm run build
```
