from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import auth, config, prompts
from app.db import init_db


def create_app(db_path: Path = config.DATABASE_PATH, static_dir: Path = config.STATIC_DIR) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(db_path)
        yield

    app = FastAPI(title="Writing Prompt Generator", lifespan=lifespan)
    app.state.db_path = db_path

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(prompts.router)

    # Serve the statically exported frontend last so /api routes take precedence.
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    return app


app = create_app()
