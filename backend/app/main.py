import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import auth, config, prompt_store, prompts
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
    warm_up_count: int = config.WARM_UP_COUNT,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(db_path)
        warmer = prompt_store.PromptWarmer(
            db_path,
            prompt_store.load_subjects(subjects_path),
            target=warm_up_count,
            generate=prompts.generate_for_subject,
        )
        app.state.prompt_warmer = warmer
        warmer.start()  # runs in the background; startup doesn't wait for the LLM
        yield
        warmer.stop()

    app = FastAPI(title="Writing Prompt Generator", lifespan=lifespan)
    app.state.db_path = db_path

    @app.get("/api/health")
    def health(db: Db) -> dict[str, str | int]:
        return {"status": "ok", "stored_prompts": prompt_store.count(db)}

    app.include_router(auth.router)
    app.include_router(prompts.router)

    # Serve the statically exported frontend last so /api routes take precedence.
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    return app


app = create_app()
