"""Candidate eligibility profile — loaded from the private vault (rule 035).

The candidate's personal attributes (nationality, driving licence, civil-servant
status, …) must never be hardcoded in the repo. They live in the vault at
`<vault>/data/candidate.yaml` (committable template: `config/candidate.example.yaml`)
and drive which job-posting requirements are disqualifying.
"""
from __future__ import annotations

import yaml

from src.core.logger import logger
from src.core.settings import DATA_DIR

CANDIDATE_FILE = DATA_DIR / "candidate.yaml"


def load_candidate() -> dict:
    """Return the `candidate` mapping from the vault's candidate.yaml.

    Returns an empty dict (with a logged warning) when the file is absent, so the
    caller applies no candidate-specific blocker instead of a hardcoded profile.
    """
    if not CANDIDATE_FILE.exists():
        logger.warning(
            f"Candidate profile not found at {CANDIDATE_FILE}; eligibility blockers "
            "that depend on it will be skipped. Copy config/candidate.example.yaml "
            "there and fill it in."
        )
        return {}
    with open(CANDIDATE_FILE, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("candidate", {}) or {}


def eligibility_blockers(candidate: dict) -> list[tuple[list[str], str]]:
    """Build the (signals, message) hard blockers active for this candidate.

    A blocker is included only when the candidate cannot satisfy that requirement.
    Signal phrases stay in French on purpose: they are matched against French-language
    job postings (they are data, not prose).
    """
    is_french = str(candidate.get("nationality", "")).strip().lower() == "french"
    blockers: list[tuple[list[str], str]] = []

    if not candidate.get("driving_licence_b", False):
        blockers.append((
            ["permis b obligatoire", "permis de conduire obligatoire",
             "permis b exigé", "permis b requis", "permis b indispensable",
             "driving license required", "driver's license required"],
            "⛔  Permis B obligatoire — profil non éligible.",
        ))

    if not candidate.get("civil_servant", False):
        blockers.append((
            ["être fonctionnaire", "titulaire de la fonction publique",
             "réservé aux agents titulaires", "fonctionnaire de catégorie",
             "mutation interne", "détachement uniquement"],
            "⛔  Poste réservé aux fonctionnaires titulaires — profil non éligible.",
        ))

    if not is_french:
        blockers.append((
            ["nationalité française obligatoire", "réservé aux ressortissants français",
             "nationalité française exigée", "être de nationalité française"],
            "⛔  Nationalité française obligatoire — profil non éligible.",
        ))
        blockers.append((
            ["habilitation secret défense", "habilitation confidentiel défense",
             "secret-défense", "accès à des informations classifiées secret"],
            "⛔  Habilitation Secret/Confidentiel Défense requise — profil non éligible.",
        ))

    return blockers
