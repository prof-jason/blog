# Backend

FastAPI app for the writing prompt generator. See the root README for how to run it.

- `app/main.py`: app factory, SQLite init on startup, static frontend mount
- `app/llm.py`: generic structured-output LLM wrapper (LiteLLM → OpenRouter)
- `app/prompts.py`: grade 4–6 instructions, batch generation, `GET /api/prompts/next`
- `app/prompt_store.py`: the prompt pool (`PromptPool`): serving, background refills
- `app/budget.py`: `RequestBudget`, the daily cap on LLM requests
- `subjects.json`: the subject list
- `app/auth.py`: signup / login / logout / me
