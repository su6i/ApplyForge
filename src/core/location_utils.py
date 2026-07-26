"""
location_utils.py — Detect job location region and select the matching CV city.

The CV city selection is data-driven via the candidate configuration.
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
    Return the city string to use in \\cvlocation.
    """
    from src.core.candidate import load_candidate
    
    candidate = load_candidate()
    loc_cfg = candidate.get("cv_location", {})
    cfg_city = loc_cfg.get("city")
    always_use = loc_cfg.get("always_use", False)
    mobility_fr = loc_cfg.get("mobility_fr")
    country = loc_cfg.get("country")

    selected = job_location.strip()
    if cfg_city:
        if always_use or is_occitanie(job_location) or is_france_travail(job_url):
            selected = cfg_city
            
    if not selected:
        return ""

    if language == "fr":
        if mobility_fr:
            return f"{selected}, {mobility_fr}"
        return selected
    else:
        if country:
            return f"{selected}, {country}"
        return selected
