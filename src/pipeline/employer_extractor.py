import json
import re
import yaml
from pathlib import Path

from src.core.llm_factory import get_llm
from src.core.logger import logger

# Try both relative and absolute paths for config
_base = Path(__file__).parent.parent.parent
CONFIG_FILE = _base / "config" / "known_agencies.yaml"

def load_known_agencies() -> list[str]:
    """Load the agency name list, complaining loudly if it is missing or empty.

    Detection still works without it (the French text signals below catch most
    intermediaries), so this must not raise — but a silent empty list would
    quietly downgrade every posting published by a *named* agency to `direct`,
    which is exactly the wrong answer to record. Warn, don't hide it.
    """
    if not CONFIG_FILE.exists():
        logger.warning(
            f"Known-agency list not found at {CONFIG_FILE} — falling back to text "
            f"signals only. Postings published by a named agency may be recorded "
            f"as direct employers."
        )
        return []
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    agencies = data.get("agencies", []) if isinstance(data, dict) else []
    if not agencies:
        logger.warning(f"{CONFIG_FILE.name} defines no agencies — check its `agencies:` key.")
    return agencies

KNOWN_AGENCIES = load_known_agencies()

def detect_intermediary(text: str) -> str | None:
    text_lower = text.lower()
    for agency in KNOWN_AGENCIES:
        # Avoid matching partial words if possible, but agency names might be complex.
        # Simple word boundary check:
        if re.search(rf"\b{re.escape(agency.lower())}\b", text_lower):
            return agency

    signals = [
        r"pour (le compte de )?notre client",
        r"notre client[, ]",
        r"l'un de nos clients",
        r"un[e]? de nos clients",
        r"cabinet de recrutement",
        r"cabinet de conseil",
        r"\besn\b",
        r"\bssii\b",
        r"société de conseil",
        r"agence d'intérim",
        r"\bintérim\b",
        r"mission d'intérim",
        r"nous recrutons pour",
        r"chez notre partenaire",
        r"client final"
    ]
    for sig in signals:
        if re.search(sig, text_lower):
            return "Detected Intermediary"
    return None

def extract_employer_info(text: str, default_company: str = "") -> dict:
    intermediary = detect_intermediary(text)
    if not intermediary and not detect_intermediary(default_company):
        return {
            "real_employer": default_company,
            "employer_type": "direct",
            "posting_via": ""
        }

    llm = get_llm(temperature=0.0)
    prompt = f"""You are an assistant that extracts the real employer from a job posting text.
A recruitment agency, ESN, or staffing firm might be the one posting the job.
Text/Context: {text}
Company field provided: {default_company}

Determine:
1. employer_type: must be one of ["direct", "agency", "esn", "staffing", "jobboard", "unknown"]
2. posting_via: the intermediary's name if employer_type != "direct", else ""
3. real_employer: the real employer / end client. If anonymised in the text, return "Client anonyme (via <intermediary_name>)". If direct, return the company name.

Return ONLY a JSON object with keys "real_employer", "employer_type", "posting_via".
"""
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(content)
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return {"real_employer": default_company, "employer_type": "unknown", "posting_via": ""}
