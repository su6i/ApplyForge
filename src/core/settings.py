"""
Application settings — all values from environment variables via .env file.
Copy .env.example to .env and fill in your keys.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Repo root (one level above src/) ────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]

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
TEMPLATES_LATO = REPO_ROOT / "templates" / "lato"
TEMPLATES_ALTACV = REPO_ROOT / "templates" / "altacv"
TEMPLATES_SHARED = REPO_ROOT / "templates" / "shared"
COVER_LETTERS_DIR = REPO_ROOT / "cover_letters"
OUTPUT_DIR = REPO_ROOT / "output"
JOB_APPLY_DIR = Path(os.getenv("JOB_APPLY_DIR", str(REPO_ROOT / "Applied")))
PHD_APPLY_DIR = Path(os.getenv("PHD_APPLY_DIR", str(REPO_ROOT / "Applied")))
APPLIED_DIR = JOB_APPLY_DIR  # legacy alias
