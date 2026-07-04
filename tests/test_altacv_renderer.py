"""
test_altacv_renderer.py — Skills section must give each category a distinct icon.

Owner review of a generated altacv FR CV found every skills category rendered with
the same icon (all \\faCode). Confirms the fix in src/pipeline/altacv_renderer.py.

Runnable two ways (pytest is optional in this repo):
    .venv/bin/python tests/test_altacv_renderer.py     # plain-python self-runner
    pytest tests/test_altacv_renderer.py                 # if pytest is installed
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly (python tests/test_altacv_renderer.py) from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.altacv_renderer import _section_skills

_SKILLS = {
    "ai_ml": ["Python", "LangChain"],
    "mlops_devops": ["Docker", "FastAPI"],
    "networks_support": ["Cisco IOS", "SNMP"],
    "data": ["Pandas", "SQL"],
}


def test_each_skill_category_gets_a_distinct_icon():
    output = _section_skills(_SKILLS, tailored_skills=[], role="ai", language="en")
    icons_used = {
        "ai_ml": r"\faRobot",
        "mlops_devops": r"\faCloud",
        "networks_support": r"\faNetworkWired",
        "data": r"\faChartLine",
    }
    for icon in icons_used.values():
        assert output.count(icon) == 1, f"expected exactly one {icon}, got {output.count(icon)}"
    # No leftover uniform fallback icon across all categories.
    assert output.count(r"\faCode") == 0


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
