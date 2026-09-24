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
`backend/subjects.json`.

### The prompt pool (why rolls are instant and quota-safe)

The app uses OpenRouter's free models, which are sometimes busy and are limited to a number of
requests **per day per account**. So rolls never wait on the AI:

- Prompts are written ahead of time into a **pool**, 10 at a time in a **single request**. The pool
  is filled at startup and refilled in the background whenever fewer than 5 unseen prompts remain,
  so it takes about 1 request per 10 rolls however many students are rolling.
- Opening the page and rolling the die both take the next card from the pool: a different subject
  from the one showing, least-shown prompts first. That's instant and costs no request.
- All AI requests share a **daily budget** (default 40, under the free tier's limit). Once it's
  spent, rolls keep working by re-showing saved prompts until it frees up.
- Only right after startup, before the first 10 prompts arrive, does the card show "Getting your
  prompt…" (it waits and retries automatically). If no prompts can be made at all, the card says so
  and a click tries again.

## Running the app

You need Docker and a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=...          # required
LLM_DAILY_REQUEST_LIMIT=40      # optional: max AI requests per 24 hours (raise it if the account has credits)
PROMPT_BATCH_SIZE=10            # optional: prompts written per request
PROMPT_REFILL_BELOW=5           # optional: refill when fewer unseen prompts than this remain
```

```bash
scripts/start-mac.sh      # or start-linux.sh / start-windows.ps1 → http://localhost:8000
scripts/stop-mac.sh       # or stop-linux.sh / stop-windows.ps1
```

By default only this computer can open the app. To let other devices on the network (for example
students' laptops) reach it, start it with `BLOG_HOST=0.0.0.0 scripts/start-mac.sh` (on Windows,
set `$env:BLOG_HOST = "0.0.0.0"` first). The container restarts automatically if it stops, runs as
a non-root user, and reports its health to Docker.

Each start uses 1 request (at most 2) to fill the pool. The database is recreated on every start,
so saved prompts and accounts don't persist.

## How it's built

- **Frontend** (`frontend/`): Next.js 16 (App Router, TypeScript, Tailwind), built as a static
  export.
  - `components/PromptStudio.tsx`: the two-step flow (card, die, loading and errors).
  - `components/PromptCard.tsx` and `lib/useCardFlip.ts`: the index card and its 3D flip animation.
  - `components/DiceRoller.tsx`: the die.
- **Backend** (`backend/`): FastAPI managed with uv. It serves the API and the exported frontend on
  one origin.
  - `app/llm.py`: a generic structured-output LLM wrapper (LiteLLM → OpenRouter `openrouter/free`).
  - `app/prompts.py`: the grade 4–6 prompt instructions, batch generation and `/api/prompts/next`.
  - `app/prompt_store.py`: the prompt pool (serving, background refills).
  - `app/budget.py`: the daily cap on AI requests.
  - `app/auth.py`: sign-up / login (not used by the UI yet).
  - SQLite tables `users`, `sessions` and `stored_prompts`.
- **Docker**: a multi-stage `Dockerfile`. Node builds the frontend, then Python serves everything.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/prompts/next?exclude=<subject>` | The next card from the pool, `{subject, prompt, example}`, for a subject other than `exclude`. Never calls the AI. `503` if the pool is empty: with `Retry-After` while prompts are being written, without it if none are coming. |
| `GET /api/health` | Status, saved and unseen prompt counts, whether a refill is running, and requests left today. |
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
