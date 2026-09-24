# Backend

FastAPI app for the writing prompt generator. See the root README for how to run it.

- `app/main.py`: app factory, SQLite init on startup, static frontend mount
- `app/llm.py`: generic structured-output LLM wrapper (LiteLLM → OpenRouter)
- `app/prompts.py`: `POST /api/prompts` (falls back to stored prompts)
- `app/prompt_store.py`: startup warm-up (`PromptWarmer`) and the stored-prompt lookup
- `app/auth.py`: signup / login / logout / me
