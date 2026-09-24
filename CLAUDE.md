# Writing Prompt Generator

## Overview

A web app that gives students in **grades 4–6** creative-writing practice. The page shows an index
card and a die:

- The **front of the card** shows a subject and an AI-generated writing prompt for it.
- **Clicking the card** flips it over (a 3D flip animation) to an example response written the way a
  strong 4th–6th grader would write it. Clicking again flips it back.
- **Rolling the die** picks a new subject, turns the card to its front, and generates that subject's
  prompt.

Prompts come from free LLMs on OpenRouter. Ten are pre-generated at startup and used as fallbacks
when live generation fails. Sign-up/login endpoints exist on the backend, but the frontend doesn't
use them yet: the app has no login.

## Development process

When instructed to build a feature:
1. Use your Github to read the feature instructions from Github issues
2. Develop the feature - do not skip any step from the feature-dev 7 step process
3. Thoroughly test the feature with unit tests and integration tests and fix any issues
4. Submit a PR using your github tools

Pull requests:
- **Always open PRs against `main`.** Don't stack a PR on another feature branch. Stacked PRs #4
  and #6 were merged into their base branches instead of `main` and had to be recovered with #8.
  If a PR depends on an unmerged one, say "merge #N first" in its description.
- The GitHub MCP token can't create PRs (403). Use the `gh` CLI instead.

## AI design

- All LLM calls go through `backend/app/llm.py`, a generic wrapper around LiteLLM → OpenRouter
  with **Structured Outputs** (a Pydantic model as `response_format`). It tolerates ```` ```json ````
  fences and text around the JSON, and raises `LLMError` (or `UnusableOutputError` for
  empty/invalid output) so callers can fall back.
- The model is **`openrouter/free`** (`MODEL = "openrouter/openrouter/free"`), OpenRouter's router
  that picks a free model per request. `provider.require_parameters` makes it choose only models
  that honor structured outputs.
  - The Cerebras skill specifies `nvidia/nemotron-3-ultra-550b-a55b:free` with Cerebras as the
    provider. Cerebras doesn't serve that model on OpenRouter (its only endpoint was Nvidia's,
    and that was often overloaded), so the project switched to `openrouter/free`. Keep the skill's
    LiteLLM/OpenRouter approach, but don't switch the model back without asking.
- `OPENROUTER_API_KEY` is in `.env` in the project root.
- **Quota:** OpenRouter's free tier limits **requests per day per account** (`free-models-per-day`),
  not output size. Protect it:
  - Startup warm-up asks for all 10 fallback prompts in **one** request, and makes at most 2.
  - Automated tests never call OpenRouter. A conftest guard fails any test that tries.
    `RUN_LIVE_LLM=1` allows exactly one real request, with no retries.
  - Avoid needless container restarts and live calls while developing.
- Card clicks give up after 20s (`LIVE_DEADLINE_SECONDS`) and serve a stored prompt. Blank or
  unusable replies fall back too.
- The model instructions (`backend/app/prompts.py`) share one `_WRITING_GUIDELINES` block that
  targets grades 4–6. Both the single-prompt and batch prompts use it, so keep grade-level changes
  there.

## Technical design

- The whole project is packaged into one Docker container (multi-stage `Dockerfile`: Node builds
  the frontend, then Python serves everything).
- The backend is in `backend/`: a uv project using FastAPI (non-packaged `app/` module).
- The frontend is in `frontend/`: Next.js 16 (App Router, TypeScript, Tailwind), statically exported
  and served by FastAPI on the same origin as `/api`. In development, `next dev` proxies `/api` to
  `:8000`.
  - Next 16 differs from older versions. Read `frontend/AGENTS.md` and the guides in
    `frontend/node_modules/next/dist/docs/` before changing Next-specific code.
- The database is SQLite, created from scratch each time the server starts. Tables: `users` and
  `sessions` (sign up / sign in) and `stored_prompts` (the startup fallbacks).
- `frontend/src/data/subjects.json` is the single subject list, shared by the die and the backend
  warm-up.
- Scripts in `scripts/`:
```bash
# Mac
scripts/start-mac.sh    # Start
scripts/stop-mac.sh     # Stop

# Linux
scripts/start-linux.sh
scripts/stop-linux.sh

# Windows
scripts/start-windows.ps1
scripts/stop-windows.ps1
```
The app is available at http://localhost:8000

## Visual design

- A ruled index card (red margin line, blue rules) on a warm paper background. The back of the card
  is blank, like a real index card. Light and dark themes are defined as CSS variables in
  `frontend/src/app/globals.css`.
- Fonts: Fraunces for headings and the subject, Newsreader for body text.
- The flip is a Web Animations API animation in `frontend/src/lib/useCardFlip.ts`: the card lifts,
  tilts, turns and settles, with a floor shadow and edge shading. Duration, lift and tilt are
  constants at the top of that file. The CSS resting transforms must match its first and last
  keyframes (a test enforces this). Users who prefer reduced motion get an instant switch.

## Progress

- **Issue #1 (PR #3, merged):** the prototype. A Next.js page with a flipping prompt card and a
  dice randomizer, using hard-coded prompts.
- **Issue #2 (PRs #4 and #6, landed on `main` via #8):** the V1 foundation. A FastAPI backend, SQLite
  with auth endpoints, the static frontend served by FastAPI, Docker and start/stop scripts, and
  LLM-generated prompts (`POST /api/prompts`). Startup pre-generates fallback prompts, and failed
  live generation serves a stored one.
- **Issue #5 (PR #9, merged):** the card flip became a physical 3D flip (lift, tilt, shadow,
  shading, blank back).
- **PR #10 (merged):** switched the model to `openrouter/free`. Added a test guard limiting real
  OpenRouter calls to one; startup warm-up in one batch request; fallbacks for blank replies; and a
  20s limit on card clicks.
- **PR #11 (open):** prompts and examples written for grades 4–6 (client feedback).
- **PR #12 (open, merge after #11):** a two-step card (client feedback). The front shows the
  subject and prompt together, a click flips to the example, and the die brings a new subject and
  prompt. The page opens on a stored prompt (`GET /api/prompts/stored`), so the first card costs no
  request.
- **Not started yet:** a login UI wired to the existing auth endpoints (nothing requires sign-in
  today).
