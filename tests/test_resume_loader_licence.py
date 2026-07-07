"""
test_resume_loader_licence.py — conditional_education must survive
generate_role_profile()'s LLM rewrite regardless of what the LLM actually
returns. Without this, --licence silently no-ops for any role whose
derived profile lost the field (found on Support, 2026-07-07; the prompt
schema simply never listed the key).

Runnable two ways (pytest is optional in this repo):
    .venv/bin/python tests/test_resume_loader_licence.py     # plain-python self-runner
    pytest tests/test_resume_loader_licence.py                 # if pytest is installed
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.resume_loader import _carry_over_conditional_education

_MASTER_WITH_LICENCE = json.dumps({
    "identity": {"name": "Test"},
    "conditional_education": [
        {"degree": "Bachelor's Degree in Electronics Engineering", "institution": "Foo"}
    ],
})


def test_llm_output_missing_the_field_gets_it_carried_over():
    # Simulates the exact bug found on Support: the LLM's parsed output
    # simply has no conditional_education key at all.
    parsed = {"identity": {"name": "Test"}, "education": []}
    result = _carry_over_conditional_education(parsed, _MASTER_WITH_LICENCE)
    assert result["conditional_education"] == [
        {"degree": "Bachelor's Degree in Electronics Engineering", "institution": "Foo"}
    ]


def test_llm_hallucinated_a_different_value_gets_overwritten():
    # Master CV is the source of truth -- an LLM-invented conditional_education
    # (wrong content, not just missing) must not survive either.
    parsed = {"conditional_education": [{"degree": "Something the LLM made up"}]}
    result = _carry_over_conditional_education(parsed, _MASTER_WITH_LICENCE)
    assert result["conditional_education"] == [
        {"degree": "Bachelor's Degree in Electronics Engineering", "institution": "Foo"}
    ]


def test_master_without_the_field_is_a_no_op():
    master_no_licence = json.dumps({"identity": {"name": "Test"}})
    parsed = {"identity": {"name": "Test"}}
    result = _carry_over_conditional_education(parsed, master_no_licence)
    assert "conditional_education" not in result


def test_malformed_master_json_does_not_crash():
    parsed = {"identity": {"name": "Test"}}
    result = _carry_over_conditional_education(parsed, "{not valid json")
    assert result == parsed


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
