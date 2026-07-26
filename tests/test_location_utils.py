"""
test_location_utils.py — Tests for data-driven CV city selection.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.location_utils import select_cv_city, is_occitanie, is_france_travail


@patch("src.core.candidate.load_candidate")
def test_select_cv_city_no_config(mock_load):
    """With no config, it falls back to the job's own location string."""
    mock_load.return_value = {}
    
    assert select_cv_city("Lyon", language="fr") == "Lyon"
    assert select_cv_city("Paris", language="en") == "Paris"
    assert select_cv_city("", language="fr") == ""


@patch("src.core.candidate.load_candidate")
def test_select_cv_city_with_config_always_use(mock_load):
    """With always_use=True, the configured city is always used."""
    mock_load.return_value = {
        "cv_location": {
            "city": "Nice",
            "always_use": True,
            "mobility_fr": "mobile dans le 06",
            "country": "France"
        }
    }
    
    # Should use 'Nice' even if job is in Lyon
    assert select_cv_city("Lyon", language="fr") == "Nice, mobile dans le 06"
    assert select_cv_city("Lyon", language="en") == "Nice, France"


@patch("src.core.candidate.load_candidate")
def test_select_cv_city_with_config_heuristic(mock_load):
    """With always_use=False, it triggers only on matching heuristic (Occitanie or France Travail)."""
    mock_load.return_value = {
        "cv_location": {
            "city": "Toulouse",
            "always_use": False,
            "mobility_fr": "mobile région",
            "country": "France"
        }
    }
    
    # No heuristic match -> falls back to job location
    assert select_cv_city("Lyon", language="fr") == "Lyon, mobile région"
    
    # Occitanie match -> uses configured city
    assert select_cv_city("Montauban", language="fr") == "Toulouse, mobile région"
    
    # France Travail match -> uses configured city
    assert select_cv_city("Paris", language="fr", job_url="https://francetravail.fr/offre/123") == "Toulouse, mobile région"


def test_occitanie_detection_still_works_if_called_directly():
    """is_occitanie helper remains functional."""
    assert is_occitanie("Montpellier")
    assert is_occitanie("Toulouse")
    assert not is_occitanie("Lyon")
    assert not is_occitanie("")


def test_france_travail_detection_still_works():
    """is_france_travail helper remains functional."""
    assert is_france_travail("https://francetravail.fr/offres/emploi")
    assert is_france_travail("https://pole-emploi.fr/offre/123")
    assert not is_france_travail("https://indeed.fr/offre/abc")
    assert not is_france_travail("")


def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
    print(f"\\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())

