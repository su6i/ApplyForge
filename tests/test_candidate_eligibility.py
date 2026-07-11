"""Eligibility blockers are derived from the candidate profile, not hardcoded."""
import sys
from pathlib import Path

# Allow running directly (python tests/test_candidate_eligibility.py) from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.candidate import eligibility_blockers


def _messages(candidate: dict) -> list[str]:
    return [msg for _signals, msg in eligibility_blockers(candidate)]


def test_no_licence_adds_permis_blocker():
    assert any("Permis B" in m for m in _messages({"driving_licence_b": False}))


def test_has_licence_removes_permis_blocker():
    assert not any("Permis B" in m for m in _messages({"driving_licence_b": True}))


def test_non_french_adds_nationality_and_clearance_blockers():
    msgs = _messages({"nationality": "canadian"})  # any non-French nationality
    assert any("Nationalité française" in m for m in msgs)
    assert any("Habilitation" in m for m in msgs)


def test_french_nationality_removes_those_blockers():
    msgs = _messages({"nationality": "french"})
    assert not any("Nationalité française" in m for m in msgs)
    assert not any("Habilitation" in m for m in msgs)


def test_non_civil_servant_adds_fonctionnaire_blocker():
    assert any("fonctionnaires" in m for m in _messages({"civil_servant": False}))


def test_empty_profile_still_returns_default_blockers():
    # An absent profile ({}) means: no licence, not a civil servant, not French →
    # every blocker is active (the conservative default).
    assert len(eligibility_blockers({})) == 4
