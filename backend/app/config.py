import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Local runs read the project-root .env; in Docker the variables come from --env-file.
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BACKEND_DIR / "data" / "app.db"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", PROJECT_ROOT / "frontend" / "out"))
SUBJECTS_PATH = Path(os.environ.get("SUBJECTS_PATH", PROJECT_ROOT / "frontend" / "src" / "data" / "subjects.json"))

# How many prompts to pre-generate at startup (in one request) as a fallback for when live
# generation fails.
WARM_UP_COUNT = int(os.environ.get("PROMPT_WARM_UP_COUNT", "10"))
