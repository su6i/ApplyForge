"""
resume_loader.py — Load role-specific candidate profiles for prompt injection.

Canonical naming for role source profiles:
    data/{CV_OWNER_SLUG}-CV_<RoleLabel>_source.json

Legacy names (data/resume_profile_<role>.json) are auto-migrated when found.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.core.logger import logger
from src.core.settings import CV_OWNER_SLUG, REPO_ROOT


_ROLE_LABEL_MAP = {
    "ai": "AI",
    "it": "IT",
    "phd": "PhD",
    "python": "Python",
    "devops": "DevOps",
}


def _normalized_role(role: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", role.lower())


def _canonical_role_label(role: str) -> str:
    normalized = _normalized_role(role).replace("_", "-")
    if normalized in _ROLE_LABEL_MAP:
        return _ROLE_LABEL_MAP[normalized]
    return role.strip().replace("_", " ").replace("-", " ").title().replace(" ", "")


def _legacy_profile_path(role: str) -> Path:
    safe_role = _normalized_role(role)
    return REPO_ROOT / "data" / f"resume_profile_{safe_role}.json"


def get_profile_path(role: str) -> Path:
    role_label = _canonical_role_label(role)
    return REPO_ROOT / "data" / f"{CV_OWNER_SLUG}-CV_{role_label}_source.json"


def _migrate_legacy_profile_if_needed(role: str) -> Path:
    canonical = get_profile_path(role)
    if canonical.exists():
        return canonical

    legacy = _legacy_profile_path(role)
    if legacy.exists():
        try:
            legacy.replace(canonical)
            logger.info(f"Migrated legacy role profile {legacy.name} -> {canonical.name}")
            return canonical
        except Exception as exc:
            logger.warning(f"Could not migrate legacy role profile {legacy.name}: {exc}")
            return legacy

    return canonical

def generate_role_profile(role: str) -> Path:
    """
    Generate a tailored JSON profile from the master_cv.json using the LLM.
    """
    master_path = REPO_ROOT / "data" / "master_cv.json"
    if not master_path.exists():
        raise FileNotFoundError(f"Ultimate Source of Truth missing: {master_path}")
        
    logger.info(f"Generating new profile for '{role}' from master_cv.json via LLM...")
    
    with master_path.open(encoding="utf-8") as fh:
        master_json_text = fh.read()
        
    from src.core.llm_factory import get_llm
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    
    # We use temperature 0.2 to allow some slight rewording for highlights 
    # but still strictly adhere to facts and JSON format.
    llm = get_llm(temperature=0.2)
    
    system_prompt = """\
You are an expert technical recruiter and resume tailor.
The user has provided their ultimate MASTER CV in a detailed JSON format.
Your task: Extract and tailor this Master CV specifically for a "{role}" position.

IMPORTANT: The output JSON MUST follow this FLAT schema (different from the Master CV's nested roles):
{{
  "identity": {{ 
     "name": "...", 
     "title": "Professional Title tailored to {role} e.g. 'DevOps Engineer' or 'AI Engineer'", 
     "email": "...", "phone": "...", "location": "...", "github": "...", "linkedin": "..." 
  }},
  "profile_summary": "rewritten for {role}",
  "skills": {{ "ai_ml": [], "mlops_devops": [], "networks_support": [], "data": [] }},
  "experience": [
    {{
      "company": "...",
      "location": "...",
      "role": "...",
      "period": "...",
      "highlights": ["max 4 highly relevant bullet points"],
      "tech": ["max 6 relevant tech"]
    }}
  ],
  "projects": [
    {{
      "title": "...",
      "period": "...",
      "description": "...",
      "highlights": ["max 4 points"],
      "tech": ["max 8 tech"]
    }}
  ],
  "education": [...],
  "languages": {{}},
  "hobbies": [],
  "certifications": []
}}

Rules:
1. Flatten the `experience`. The Master CV has nested `roles`; you MUST return a flat list of job dicts.
2. Filter/reorder `skills` to emphasize those relevant to "{role}".
3. For `projects`, select ONLY the 2 or 3 most relevant.
4. Rewrite the `profile_summary` to position the candidate strongly for "{role}".
5. For `profile_summary`, strictly follow:
    "Éviter de mettre des métriques dans ton profil (-70% d'intervention manuelles,
    + 500% de vitesse). A réserver pour les expériences professionnelles."
    So do NOT include percentages or quantified uplift/reduction metrics in profile_summary.
6. Start immediately with {{. Return ONLY valid JSON."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Master CV JSON:\n{master_json}\n\nReturn tailored JSON for: {role}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    raw_output = chain.invoke({
        "role": role,
        "master_json": master_json_text
    })
    
    # Clean possible markdown block wrappers
    clean_json = re.sub(r"^```(?:json)?\s*", "", raw_output.strip(), flags=re.MULTILINE)
    clean_json = re.sub(r"```\s*$", "", clean_json.strip())
    
    try:
        parsed = json.loads(clean_json)
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse LLM JSON for role '{role}':\n{clean_json}")
        raise ValueError(f"LLM returned invalid JSON for the '{role}' profile.") from exc
        
    out_path = get_profile_path(role)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(parsed, fh, indent=2, ensure_ascii=False)
        
    logger.success(f"Successfully generated profile: {out_path.name}")
    return out_path


@lru_cache(maxsize=4)
def load_profile(role: str = "ai") -> dict[str, Any]:
    """
    Load and cache canonical role source profile JSON.
    If it doesn't exist, trigger generation from `master_cv.json`.
    """
    profile_path = _migrate_legacy_profile_if_needed(role)
    
    if not profile_path.exists():
        logger.info(f"Profile {profile_path.name} not found. Triggering generation...")
        profile_path = generate_role_profile(role)
            
    with profile_path.open(encoding="utf-8") as fh:
        profile = json.load(fh)
    logger.debug(f"Resume profile ({role}) loaded from {profile_path}")
    return profile


def format_for_prompt(role: str = "ai") -> str:
    """
    Return a compact, token-efficient text representation of the candidate
    profile, suitable for injection into system or human prompts.

    Example output (truncated):
        === CANDIDATE PROFILE ===
        Name : Firstname LASTNAME
        Title: AI Engineer & Data Scientist
        Location: Montpellier, France
        ...
    """
    p = load_profile(role)

    identity = p.get("identity", {})
    skills   = p.get("skills", {})
    exp      = p.get("experience", [])
    projects = p.get("projects", [])
    edu      = p.get("education", [])
    certs    = p.get("certifications", [])

    lines: list[str] = ["=== CANDIDATE PROFILE ==="]

    # Identity
    lines.append(f"Name    : {identity.get('name', 'N/A')}")
    lines.append(f"Title   : {identity.get('title', 'N/A')}")
    lines.append(f"Location: {identity.get('location', 'N/A')}")

    # Summary
    summary = p.get("profile_summary", "")
    if summary:
        lines.append(f"\nSummary: {summary}")

    # Skills (flat list, tokenized efficiently)
    lines.append("\nKey skills:")
    for category, skill_list in skills.items():
        lines.append(f"  {category}: {', '.join(skill_list)}")

    # Experience
    lines.append("\nExperience:")
    for job in exp:
        lines.append(
            f"  [{job.get('period', '')}] {job.get('role', '')} @ {job.get('company', '')}, {job.get('location', '')}"
        )
        for h in job.get("highlights", []):
            lines.append(f"    • {h}")

    # Projects
    lines.append("\nKey projects:")
    for proj in projects:
        tech = ", ".join(proj.get("tech", []))
        lines.append(f"  {proj.get('title', '')} ({proj.get('period', '')}): {proj.get('description', '')} | Tech: {tech}")

    # Education
    lines.append("\nEducation:")
    for edu_item in edu:
        lines.append(
            f"  {edu_item.get('degree', '')} — {edu_item.get('institution', '')} ({edu_item.get('period', '')})"
        )
        if edu_item.get("honors"):
            lines.append(f"    Honors: {edu_item['honors']}")

    # Conditional education (only shown to LLM, not always on CV)
    cond_edu = p.get("conditional_education", [])
    if cond_edu:
        lines.append("\nConditional education (include in extra_education ONLY if job domain matches relevant_domains):")
        for ce in cond_edu:
            domains = ", ".join(ce.get("relevant_domains", []))
            lines.append(
                f"  {ce.get('degree', '')} — {ce.get('institution', '')} ({ce.get('period', '')}) | GPA: {ce.get('gpa', '')} | relevant_domains: [{domains}]"
            )
            if ce.get("honors"):
                lines.append(f"    Honors: {ce['honors']}")

    # Languages & Certifications
    lang_str = ", ".join(f"{k} ({v})" for k, v in p.get("languages", {}).items())
    lines.append(f"\nLanguages: {lang_str}")
    if certs:
        lines.append(f"Certifications: {'; '.join(certs)}")

    lines.append("=== END OF PROFILE ===")
    return "\n".join(lines)
