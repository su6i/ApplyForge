"""
Application settings — all values from environment variables via .env file.
Copy .env.example to .env and fill in your keys.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Repo root (one level above src/) ────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]


# ─── Personal-data vault (outside the repo) ──────────────────────────────────
# Personal data (CV profiles, master CVs, tracker DB, personal_data.tex) must
# never live inside the public repo. It is stored in a central vault outside the
# tree. Resolution order:
#   1. APPLYFORGE_DATA_DIR  — explicit override
#   2. $XDG_DATA_HOME       — XDG base dir spec
#   3. ~/.local/share       — XDG default
# under .../agent-projects/applyforge/
def _data_home() -> Path:
    override = os.getenv("APPLYFORGE_DATA_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.getenv("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "agent-projects" / "applyforge"


DATA_HOME = _data_home()

# Secrets (.env) live in the vault's secrets/, never in the repo.
load_dotenv(DATA_HOME / "secrets" / ".env")

# ─── LLM ─────────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
FALLBACK_MODEL: str = os.getenv("FALLBACK_MODEL", "gemini-1.5-flash")

# ─── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ─── Behaviour ────────────────────────────────────────────────────────────────
# When True: applications are archived immediately without asking for approval.
AUTO_APPLY: bool = os.getenv("AUTO_APPLY", "false").lower() == "true"

# ─── Owner identity (used for generated filenames — keep generic for public repo)
CV_OWNER_SLUG: str = os.getenv("CV_OWNER_SLUG", "cv-owner")

# ─── Paths ────────────────────────────────────────────────────────────────────
# Personal data → vault; template code stays in the repo.
DATA_DIR = DATA_HOME / "data"
TEMPLATES_SHARED = DATA_HOME / "shared"          # personal_data.tex/json (personal)
TEMPLATES_LATO = REPO_ROOT / "templates" / "lato"
TEMPLATES_ALTACV = REPO_ROOT / "templates" / "altacv"
COVER_LETTERS_DIR = REPO_ROOT / "cover_letters"
OUTPUT_DIR = REPO_ROOT / "output"
JOB_APPLY_DIR = Path(os.getenv("JOB_APPLY_DIR", str(REPO_ROOT / "Applied")))
PHD_APPLY_DIR = Path(os.getenv("PHD_APPLY_DIR", str(REPO_ROOT / "Applied")))
APPLIED_DIR = JOB_APPLY_DIR  # legacy alias
