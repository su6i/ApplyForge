"""
test_technicien_adapter.py — the DU-drop/honors-filter heuristic must not
fire on an HR pay-grade label or scraper noise; only on signals that
actually describe the required education/experience level.

Runnable two ways (pytest is optional in this repo):
    .venv/bin/python tests/test_technicien_adapter.py     # plain-python self-runner
    pytest tests/test_technicien_adapter.py                 # if pytest is installed
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.technicien_adapter import is_technicien_tier


def test_qualification_field_alone_does_not_trigger():
    # Regression (Lùkla, 2026-07-06): France Travail's structured
    # "Qualification : Technicien" pay-grade field is an HR/collective-
    # bargaining classification, not a description of required education —
    # a "DevOps Junior" role doing real Ansible/Terraform/Docker work must
    # not lose its DU degree just because of this administrative label.
    body = (
        "POSTE : DevOps Junior H/F\n"
        "Maintenir et faire évoluer les scripts d'automatisation (Ansible, Terraform).\n"
        "Informations complémentaires\nQualification :\nTechnicien\n"
        "Secteur d'activité :\nGestion d'installations informatiques\n"
    )
    assert is_technicien_tier(body, "DevOps Junior H/F") is False


def test_unrelated_related_offer_title_does_not_trigger():
    # Regression (CAT-AMANIA, 2026-07-06): an unrelated "Technicien système
    # (H/F)" listing leaking in from a scraped "related offers" sidebar must
    # not affect a real Cadre-tier posting's own tailoring.
    body = (
        "Tu es Ingénieur DevOps débutant et tu souhaites évoluer.\n"
        "Qualification : Cadre\n"
        "D'autres offres peuvent vous intéresser :\nTechnicien système (H/F)\nARTEMYS\n"
    )
    assert is_technicien_tier(body, "DevOps Junior - CDI - F/H") is False


def test_explicit_bac2_requirement_triggers():
    body = "Profil recherché : Bac+2 en réseaux informatiques exigé, débutant accepté."
    assert is_technicien_tier(body, "Support Informatique H/F") is True


def test_technicien_in_title_triggers():
    assert is_technicien_tier("", "Technicien Support Informatique H/F") is True


def test_ingenieur_title_guard_wins_over_body_signals():
    body = "Bac+2 accepté, poste ouvert aux profils Technicien."
    assert is_technicien_tier(body, "Ingénieur DevOps Junior") is False


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
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
