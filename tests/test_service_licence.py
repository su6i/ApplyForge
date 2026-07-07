"""
test_service_licence.py — --licence must never silently no-op. If the role's
profile has no conditional_education to inject, it must fail loudly
(LicenceProfileMissingError -> non-zero exit), not generate a CV that's
silently missing the degree the caller asked for.

Runnable two ways (pytest is optional in this repo):
    .venv/bin/python tests/test_service_licence.py     # plain-python self-runner
    pytest tests/test_service_licence.py                 # if pytest is installed
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.service import LicenceProfileMissingError, _resolve_licence_education


def test_missing_conditional_education_raises_loudly():
    profile = {"identity": {"name": "Test"}}  # no conditional_education key at all
    try:
        _resolve_licence_education(profile, role="support")
    except LicenceProfileMissingError as exc:
        assert "support" in str(exc)
        assert "conditional_education" in str(exc)
    else:
        raise AssertionError("expected LicenceProfileMissingError, --licence would have silently no-op'd")


def test_empty_conditional_education_list_also_raises():
    profile = {"conditional_education": []}
    try:
        _resolve_licence_education(profile, role="python")
    except LicenceProfileMissingError:
        pass
    else:
        raise AssertionError("expected LicenceProfileMissingError for empty conditional_education list")


def test_present_conditional_education_is_returned_verbatim():
    entries = [{"degree": "Licence en Génie Électronique (Bac+2+2)", "institution": "Foo"}]
    profile = {"conditional_education": entries}
    result = _resolve_licence_education(profile, role="python")
    assert result == entries
    # Must be a copy, not the same list object (caller mutates content.extra_education)
    assert result is not entries


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
