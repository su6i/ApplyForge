"""
resume_parser.py — Parse/refresh canonical role profile JSON from a CV file.

Supported input formats:
    .tex              — LaTeX source (read directly as text)
    .pdf              — PDF file (text extracted with pdfminer.six)
    .jpg/.jpeg/.png/.webp — Image (OCR via pytesseract + Pillow)

Run via:
    python main.py init-profile [--cv-path path/to/CV.tex|.pdf|.jpg]

If --cv-path is omitted, the default is templates/lato/CV_AI_en.tex.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.core.logger import logger
from src.core.settings import CV_OWNER_SLUG, LLM_MODEL, OPENAI_API_KEY, REPO_ROOT

PROFILE_PATH = REPO_ROOT / "data" / f"{CV_OWNER_SLUG}-CV_AI_source.json"
DEFAULT_CV_TEX = REPO_ROOT / "templates" / "lato" / "CV_AI_en.tex"

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM = """\
You are a resume data extractor. Given the raw LaTeX source of a CV, extract
all information and return it as a single valid JSON object with the following
schema (fill in exactly what you find; use empty strings/lists if missing):

{{
  "_updated": "<today's date YYYY-MM-DD>",
  "identity": {{
    "name": "", "title": "", "email": "", "phone": "",
    "location": "", "github": "", "linkedin": ""
  }},
  "profile_summary": "<one paragraph>",
  "skills": {{
    "ai_ml": [],
    "data": [],
    "mlops_infra": [],
    "visualization": [],
    "languages_prog": []
  }},
  "experience": [
    {{
      "company": "", "location": "", "role": "", "period": "",
      "highlights": [], "tech": []
    }}
  ],
  "projects": [
    {{
      "title": "", "type": "", "period": "",
      "description": "", "tech": []
    }}
  ],
  "education": [
    {{
      "degree": "", "institution": "", "period": "", "honors": ""
    }}
  ],
  "languages": {{ "<lang>": "<level>" }},
  "certifications": []
}}

Rules:
- Return ONLY the JSON. No markdown fences, no explanation.
- Clean up LaTeX commands (\\textbf{{}}, \\emph{{}}, etc.) — return plain text.
- `tech` arrays should list technology names only (no prose).
- If unsure about a field, use an empty string or empty list.
"""

_HUMAN = """\
LaTeX CV source:
---
{cv_text}
---
Return the JSON:"""


# ── Input extraction helpers ─────────────────────────────────────────────────

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _extract_text(cv_path: Path) -> str:
    """Return plain text from a .tex, .pdf, or image file."""
    ext = cv_path.suffix.lower()

    if ext == ".tex":
        return cv_path.read_text(encoding="utf-8")

    if ext == ".pdf":
        try:
            from pdfminer.high_level import extract_text as _pdf_extract
        except ImportError as exc:
            raise ImportError(
                "pdfminer.six is required for PDF support: pip install pdfminer.six"
            ) from exc
        logger.info("Extracting text from PDF via pdfminer…")
        return _pdf_extract(str(cv_path)) or ""

    if ext in _IMAGE_EXTS:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise ImportError(
                "pytesseract and Pillow are required for image OCR: "
                "pip install pytesseract Pillow"
            ) from exc
        logger.info(f"Running OCR on image ({ext}) via pytesseract…")
        return pytesseract.image_to_string(Image.open(cv_path), lang="fra+eng")

    raise ValueError(
        f"Unsupported file type '{ext}'. "
        "Supported: .tex, .pdf, .jpg, .jpeg, .png, .webp"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def parse_cv_to_profile(cv_path_arg: Path | None = None) -> dict:
    """
    Read a CV file (LaTeX / PDF / image), ask the LLM to extract structured
    data, write to the canonical AI role source JSON profile, and return the parsed dict.

    Parameters
    ----------
    cv_path_arg : path to the source file (defaults to CV_AI_en.tex).
                  Supported formats: .tex, .pdf, .jpg, .jpeg, .png, .webp
    """
    cv_path = Path(cv_path_arg) if cv_path_arg else DEFAULT_CV_TEX

    if not cv_path.exists():
        raise FileNotFoundError(f"CV file not found: {cv_path}")

    logger.info(f"Reading CV source: {cv_path}")
    cv_text = _extract_text(cv_path)

    # Truncate to avoid token overflow (first 12 000 chars should cover all)
    cv_text = cv_text[:12_000]

    from src.core.llm_factory import get_llm

    llm = get_llm(temperature=0)

    prompt = ChatPromptTemplate.from_messages(
        [("system", _SYSTEM), ("human", _HUMAN)]
    )
    chain = prompt | llm | StrOutputParser()

    logger.info("Extracting profile via LLM…")
    raw_output: str = chain.invoke({"cv_text": cv_text}).strip()

    # Strip any accidental markdown fences
    raw_output = re.sub(r"^```(?:json)?\n?", "", raw_output)
    raw_output = re.sub(r"\n?```$", "", raw_output)

    try:
        profile: dict = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        logger.error(f"LLM returned invalid JSON: {exc}\nRaw:\n{raw_output[:500]}")
        raise ValueError("LLM did not return valid JSON for the resume profile.") from exc

    # Preserve any manual comment fields from the existing file
    profile["_comment"] = "Source of truth for the candidate's profile. Feed this to the LLM for tailored applications."

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_PATH.open("w", encoding="utf-8") as fh:
        json.dump(profile, fh, ensure_ascii=False, indent=2)

    logger.info(f"Profile saved to {PROFILE_PATH}")
    return profile
