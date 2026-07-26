"""
test_content_tailor.py — Regression tests for LLM-output post-processing.

Runnable two ways (pytest is optional in this repo):
    .venv/bin/python tests/test_content_tailor.py     # plain-python self-runner
    pytest tests/test_content_tailor.py                # if pytest is installed
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly (python tests/test_content_tailor.py) from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.content_tailor import _strip_years_and_metrics, _parse_json, TailoringError
from src.core.tex_utils import latex_escape


def test_approx_metrics_survive_intact():
    # Bug: "~80%" lost its number and became a bare "~" (Inria_AI_fr regression).
    text = "Réduction du temps d'analyse de ~80% et du coût API de ~85%."
    cleaned = _strip_years_and_metrics(text)
    assert "~80%" in cleaned
    assert "~85%" in cleaned


def test_fabricated_bare_metrics_still_stripped():
    # Anti-hallucination guard must still remove metrics with no '~' marker.
    text = "Amélioration de 40% de la productivité, sur 7 ans d'expérience."
    cleaned = _strip_years_and_metrics(text)
    assert "40%" not in cleaned
    assert "7" not in cleaned or "ans" not in cleaned


def test_approx_metrics_survive_latex_escaping():
    # CV highlights go through latex_escape directly (no metric-stripping step) —
    # confirm the tilde escape itself never drops the following number.
    text = "~80% faster, ~85% lower API cost"
    escaped = latex_escape(text)
    assert "80" in escaped
    assert "85" in escaped
    assert r"\%" in escaped


def test_years_strip_keeps_trailing_clause():
    """The years phrase alone is removed — the clause after it must survive.

    The old greedy `[^,.]*` tail reduced this whole string to ''.
    """
    text = "3 ans de développement sur des architectures cloud en supervision 24/7"
    cleaned = _strip_years_and_metrics(text)
    assert "architectures cloud" in cleaned
    assert "supervision" in cleaned


def test_years_strip_keeps_clause_after_avec():
    """Regression: 'avec N ans d'expérience en …' must keep the trailing clause."""
    text = "Candidat avec 3 ans d'expérience en développement et infrastructure"
    cleaned = _strip_years_and_metrics(text)
    assert "Candidat" in cleaned
    assert "développement et infrastructure" in cleaned


def test_metric_strip_does_not_break_french():
    """Regression: 'Réduction de 70% des interventions manuelles' -> 'Réduction des interventions manuelles'."""
    text = "Réduction de 70% des interventions manuelles"
    cleaned = _strip_years_and_metrics(text)
    assert "de des" not in cleaned
    assert "des interventions manuelles" in cleaned


def test_years_strip_preserves_trailing_clause():
    """Regression: 'J'ai 3 ans d'expérience en réseaux, puis un Master.' must keep ending."""
    text = "J'ai 3 ans d'expérience en réseaux, puis un Master."
    cleaned = _strip_years_and_metrics(text)
    assert "puis un Master." in cleaned
    assert "en réseaux" in cleaned


def test_malformed_json_raises_tailoring_error():
    """_parse_json must raise TailoringError on invalid JSON."""
    raw = "not even close to json"
    try:
        _parse_json(raw)
        assert False, "Expected TailoringError"
    except TailoringError as e:
        assert "Failed to parse" in str(e)
        assert "not even close" in str(e)


def test_malformed_json_with_fences():
    """Even with code fences, invalid content must raise TailoringError."""
    raw = "```\nthis is not json\n```"
    try:
        _parse_json(raw)
        assert False, "Expected TailoringError"
    except TailoringError:
        pass


def test_empty_json_like_still_raises():
    """Empty or blank must raise."""
    try:
        _parse_json("")
        assert False, "Expected TailoringError"
    except TailoringError:
        pass


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
