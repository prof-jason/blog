import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Local runs read the project-root .env; in Docker the variables come from --env-file.
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BACKEND_DIR / "data" / "app.db"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", PROJECT_ROOT / "frontend" / "out"))
SUBJECTS_PATH = Path(os.environ.get("SUBJECTS_PATH", PROJECT_ROOT / "frontend" / "src" / "data" / "subjects.json"))


def warm_up_count(environ: Mapping[str, str] = os.environ) -> int:
    """How many prompts to pre-generate at startup as a fallback for when live generation fails.

    Each one spends OpenRouter's daily free-model quota, so development and testing default to 1;
    APP_ENV=production defaults to 10. PROMPT_WARM_UP_COUNT overrides both.
    """
    if "PROMPT_WARM_UP_COUNT" in environ:
        return int(environ["PROMPT_WARM_UP_COUNT"])
    return 10 if environ.get("APP_ENV") == "production" else 1


WARM_UP_COUNT = warm_up_count()
