"""
technicien_adapter.py — Deterministic post-processing for Technicien-tier job postings.

Applied after LLM tailoring when the posting signals catégorie B / Bac+2-3 level.
No LLM calls — pure rule-based transformations:
  1. Drop Diplôme Universitaire (overqualification signal for support/technicien roles)
  2. Filter Master honors: keep only Réseaux / Systèmes / Linux modules
  3. Normalize experience titles: Ingénieur → Technicien / Spécialiste
  4. Align CV tagline: replace Ingénieur with Technicien
"""
from __future__ import annotations

import re
from copy import deepcopy

# Keywords in job posting body that identify technicien-tier roles
_TECHNICIEN_SIGNALS = [
    "technicien", "technicienne",
    "catégorie b", "cat. b", "catégorie b ",
    "bac+2", "bac+3", "bac + 2", "bac + 3",
    "assistant informatique", "aide-technicien",
]

# Education degree substrings that signal overqualification for technicien roles
_DEGREES_TO_DROP = [
    "diplôme universitaire",
    "university diploma",
    "du en ",
    "du in ",
    "(du)",
]

# Master honors clauses: keep a clause only if it contains one of these keywords
_HONORS_KEEP_KEYWORDS = [
    "réseau", "réseau", "network",
    "système", "systèmes", "systems", "linux",
    "infrastructure",
]

# Experience role title replacements (FR and EN variants)
_ROLE_REPLACEMENTS: list[tuple[str, str]] = [
    ("Ingénieur Réseaux & Développeur Python", "Technicien Réseaux & Automatisation Python"),
    ("Ingénieur Systèmes & Réseaux",           "Technicien Systèmes & Réseaux"),
    ("Network Engineer & Python Developer",     "Technicien Réseaux & Python"),
    ("Network Engineer",                        "Technicien Réseaux"),
]


def is_technicien_tier(body: str, title: str = "") -> bool:
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["ingénieur", "architecte", "développeur", "developer", "engineer"]):
        return False
    body_lower = body.lower()
    return any(sig in body_lower for sig in _TECHNICIEN_SIGNALS)


def apply(profile: dict, content) -> tuple[dict, object]:
    """
    Return (modified_profile, modified_content) with technicien-tier rules applied.
    Inputs are deep-copied — originals are not mutated.
    """
    profile = deepcopy(profile)

    _filter_education_in_profile(profile)
    _filter_selected_education(content)
    _filter_master_honors_in_profile(profile)
    _filter_master_honors_in_selected(content)
    _normalize_experience_titles(content)
    _normalize_tagline(content)

    return profile, content


# ─── helpers ─────────────────────────────────────────────────────────────────

def _is_du(degree: str) -> bool:
    d = degree.lower()
    return any(sig in d for sig in _DEGREES_TO_DROP)


def _filter_honors(honors: str) -> str:
    """Keep only semicolon-separated clauses that mention réseaux/systèmes/linux."""
    if not honors:
        return honors
    clauses = [c.strip() for c in re.split(r"[;,]", honors)]
    kept = [c for c in clauses if any(kw in c.lower() for kw in _HONORS_KEEP_KEYWORDS)]
    return " ; ".join(kept) if kept else honors  # fallback: keep all if nothing matched


def _is_master(degree: str) -> bool:
    d = degree.lower()
    return "master" in d or "bac+5" in d or "bac +5" in d or "bac + 5" in d


def _filter_education_in_profile(profile: dict) -> None:
    profile["education"] = [
        edu for edu in profile.get("education", [])
        if not _is_du(edu.get("degree", ""))
    ]


def _filter_selected_education(content) -> None:
    if not getattr(content, "selected_education", None):
        return
    content.selected_education = [
        edu for edu in content.selected_education
        if not _is_du(edu.get("degree", ""))
    ]


def _filter_master_honors_in_profile(profile: dict) -> None:
    for edu in profile.get("education", []):
        if _is_master(edu.get("degree", "")):
            edu["honors"] = _filter_honors(edu.get("honors", ""))


def _filter_master_honors_in_selected(content) -> None:
    for edu in getattr(content, "selected_education", []) or []:
        if _is_master(edu.get("degree", "")):
            edu["honors"] = _filter_honors(edu.get("honors", ""))


def _normalize_experience_titles(content) -> None:
    for exp in getattr(content, "selected_experience", []) or []:
        role = exp.get("role", "")
        for old, new in _ROLE_REPLACEMENTS:
            role = role.replace(old, new)
        # Generic fallback: any remaining "Ingénieur" at start of title
        role = re.sub(r"^Ingénieur\b", "Technicien", role)
        exp["role"] = role


def _normalize_tagline(content) -> None:
    tagline = getattr(content, "cv_tagline", "") or ""
    tagline = re.sub(r"\bIngénieur\b", "Technicien", tagline)
    content.cv_tagline = tagline
