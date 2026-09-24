import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import auth, config, prompt_store, prompts
from app.budget import RequestBudget
from app.db import Db, init_db

# Uvicorn only configures its own loggers; without this, INFO logs from app.* are dropped.
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.setLevel(logging.INFO)
    _app_logger.propagate = False


def create_app(
    db_path: Path = config.DATABASE_PATH,
    static_dir: Path = config.STATIC_DIR,
    subjects_path: Path = config.SUBJECTS_PATH,
    batch_size: int = config.BATCH_SIZE,
    refill_below: int = config.REFILL_BELOW,
    daily_request_limit: int = config.DAILY_REQUEST_LIMIT,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(db_path)
        pool = prompt_store.PromptPool(
            db_path,
            prompt_store.load_subjects(subjects_path),
            generate_batch=prompts.generate_batch,
            budget=RequestBudget(daily_request_limit),
            batch_size=batch_size,
            refill_below=refill_below,
        )
        app.state.prompt_pool = pool
        pool.start()  # fills the pool in the background; startup doesn't wait for the LLM
        yield
        pool.stop()

    app = FastAPI(title="Writing Prompt Generator", lifespan=lifespan)
    app.state.db_path = db_path

    @app.get("/api/health")
    def health(db: Db) -> dict[str, str | int | bool]:
        pool: prompt_store.PromptPool = app.state.prompt_pool
        return {
            "status": "ok",
            "stored_prompts": prompt_store.count(db),
            "unserved_prompts": prompt_store.count_unserved(db),
            "refilling": pool.refilling,
            "requests_left_today": pool.budget.remaining(),
        }

    app.include_router(auth.router)
    app.include_router(prompts.router)

    # Serve the statically exported frontend last so /api routes take precedence.
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    return app


app = create_app()
