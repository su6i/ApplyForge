"""
location_utils.py — Detect job location region and select the matching CV city.

Rule:
  Job posted on France Travail → Montpellier (owner's registered jobseeker
                                  domicile there — must stay consistent
                                  regardless of the job's own city)
  Occitanie region              → Montpellier
  Anywhere else                 → REDACTED-CITY
"""
from __future__ import annotations

# Job-board domains where the owner is registered under a specific commune —
# that registration must win over the job's own location.
_FRANCE_TRAVAIL_DOMAINS: frozenset[str] = frozenset({
    "francetravail.fr", "pole-emploi.fr",
})

# Occitanie departments (INSEE codes) and their main cities
_OCCITANIE_CITIES: frozenset[str] = frozenset({
    # Hérault (34)
    "montpellier", "sète", "béziers", "agde", "lunel", "lodève",
    # Haute-Garonne (31)
    "toulouse", "muret", "saint-gaudens",
    # Gard (30)
    "nîmes", "alès", "uzès", "nimes", "ales",
    # Pyrénées-Orientales (66)
    "perpignan", "canet-en-roussillon",
    # Hérault (34) — more
    "palavas-les-flots", "frontignan", "mauguio", "lattes",
    # Aude (11)
    "carcassonne", "narbonne", "limoux",
    # Aveyron (12)
    "rodez", "millau", "villefranche-de-rouergue",
    # Tarn (81)
    "albi", "castres", "gaillac",
    # Tarn-et-Garonne (82)
    "montauban",
    # Lot (46)
    "cahors", "figeac",
    # Gers (32)
    "auch",
    # Ariège (09)
    "foix", "pamiers",
    # Lozère (48)
    "mende",
    # Hautes-Pyrénées (65)
    "tarbes", "lourdes",
    # Region name itself
    "occitanie", "languedoc", "midi-pyrénées", "midi-pyrenees",
})

# Postal code prefixes for Occitanie departments
_OCCITANIE_DEPT_PREFIXES: frozenset[str] = frozenset({
    "09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82",
})


def is_occitanie(job_location: str) -> bool:
    """Return True if the job location is in the Occitanie region."""
    if not job_location:
        return False
    loc = job_location.lower().strip()
    # Direct city/region name match
    for city in _OCCITANIE_CITIES:
        if city in loc:
            return True
    # Postal code in text (e.g. "34000", "31000")
    import re
    for code in re.findall(r"\b(\d{5})\b", loc):
        if code[:2] in _OCCITANIE_DEPT_PREFIXES:
            return True
    return False


def is_france_travail(job_url: str) -> bool:
    """Return True if the job posting comes from France Travail / Pôle Emploi."""
    if not job_url:
        return False
    from urllib.parse import urlparse
    netloc = urlparse(job_url.lower()).netloc
    return any(domain in netloc for domain in _FRANCE_TRAVAIL_DOMAINS)


def select_cv_city(job_location: str, language: str = "fr", job_url: str = "") -> str:
    """
    Return the city string to use in \\cvlocation based on job location.

    France Travail source → Montpellier (owner's registered domicile there,
                             must stay consistent regardless of job city)
    Occitanie region       → Montpellier
    Elsewhere              → REDACTED-CITY
    """
    if is_france_travail(job_url) or is_occitanie(job_location):
        return "Montpellier, mobile en France" if language == "fr" else "Montpellier, France"
    return "REDACTED-CITY, mobile en France" if language == "fr" else "REDACTED-CITY, France"
