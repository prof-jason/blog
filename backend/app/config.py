import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Local runs read the project-root .env; in Docker the variables come from --env-file.
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BACKEND_DIR / "data" / "app.db"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", PROJECT_ROOT / "frontend" / "out"))
SUBJECTS_PATH = Path(os.environ.get("SUBJECTS_PATH", BACKEND_DIR / "subjects.json"))

# Prompts per generation request (one batch request fills the pool at startup and on each refill).
BATCH_SIZE = int(os.environ.get("PROMPT_BATCH_SIZE", "10"))
# Refill the pool in the background when fewer than this many prompts haven't been served yet.
REFILL_BELOW = int(os.environ.get("PROMPT_REFILL_BELOW", "5"))
# Hard cap on OpenRouter requests per rolling 24 hours, whatever the traffic. The free tier limits
# requests per day per account; raise this if the account has credits.
DAILY_REQUEST_LIMIT = int(os.environ.get("LLM_DAILY_REQUEST_LIMIT", "40"))
