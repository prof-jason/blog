# Writing Prompt Generator

Creative-writing practice for students in **grades 4–6**. Each card gives students a subject and a
writing prompt to respond to, with an example response on the back to show what a strong answer
looks like.

## How it works

1. **Read the card.** The front of the index card shows a **subject** (like "A Map" or "The Night
   Sky") and a **writing prompt** about it.
2. **Flip the card** by clicking it to see an **example response**, written the way a strong 4th–6th
   grader would write it. Click again to flip back.
3. **Roll the die** for a new subject. The card turns back to its front and a new prompt is written
   for that subject.

Prompts and examples are written by an AI and pitched at grades 4–6: everyday words, short
sentences, topics kids that age know (school, friends, family, pets, games, nature, make-believe),
and 60–100-word examples in a kid's own voice. There are 30 subjects, listed in
`frontend/src/data/subjects.json`.

### When the AI is slow or unavailable

The app uses OpenRouter's free models, which are sometimes busy and are limited to a number of
requests per day. To keep a prompt on the card anyway:

- At startup, the app pre-generates **10 prompts in a single request** and saves them.
- The page opens on one of those saved prompts, so the first card appears instantly and costs no
  request.
- If a new prompt fails or takes longer than **20 seconds**, the card shows a saved prompt instead
  (for the same subject if possible), labeled "Saved prompt". It shows an error only if nothing is
  saved yet, and clicking the card then tries again.

## Running the app

You need Docker and a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=...          # required
PROMPT_WARM_UP_COUNT=10         # optional: prompts to pre-generate at startup (default 10)
```

```bash
scripts/start-mac.sh      # or start-linux.sh / start-windows.ps1 → http://localhost:8000
scripts/stop-mac.sh       # or stop-linux.sh / stop-windows.ps1
```

Each start uses 1 request (at most 2) to pre-generate the saved prompts. The database is recreated
on every start, so saved prompts and accounts don't persist.

## How it's built

- **Frontend** (`frontend/`): Next.js 16 (App Router, TypeScript, Tailwind), built as a static
  export.
  - `components/PromptStudio.tsx`: the two-step flow (card, die, loading and errors).
  - `components/PromptCard.tsx` and `lib/useCardFlip.ts`: the index card and its 3D flip animation.
  - `components/DiceRoller.tsx`: the die.
- **Backend** (`backend/`): FastAPI managed with uv. It serves the API and the exported frontend on
  one origin.
  - `app/llm.py`: a generic structured-output LLM wrapper (LiteLLM → OpenRouter `openrouter/free`).
  - `app/prompts.py`: the grade 4–6 prompt instructions and the prompt endpoints.
  - `app/prompt_store.py`: startup pre-generation and saved-prompt lookup.
  - `app/auth.py`: sign-up / login (not used by the UI yet).
  - SQLite tables `users`, `sessions` and `stored_prompts`.
- **Docker**: a multi-stage `Dockerfile`. Node builds the frontend, then Python serves everything.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/prompts/stored` | A random saved prompt (404 if none yet). Used for the opening card. |
| `POST /api/prompts` `{subject}` | `{subject, prompt, example, source}`. `source` is `live`, or `stored` for a fallback (which may be for a different subject). |
| `GET /api/health` | Status and the number of saved prompts. |
| `POST /api/auth/signup`, `/login`, `/logout`, `GET /api/auth/me` | Cookie-session accounts (no UI yet). |

## Development

```bash
# Backend (http://localhost:8000)
cd backend && uv run uvicorn app.main:app --reload

# Frontend (http://localhost:3000). next dev proxies /api to :8000
cd frontend && npm install && npm run dev
```

## Tests

```bash
cd backend && uv run pytest                  # never calls OpenRouter (a guard fails any test that tries)
cd backend && RUN_LIVE_LLM=1 uv run pytest   # plus exactly ONE real OpenRouter request, no retries
cd frontend && npm test                      # Vitest + Testing Library
cd frontend && npm run lint && npm run build
```
