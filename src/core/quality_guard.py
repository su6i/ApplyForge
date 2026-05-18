"""
quality_guard.py — Automated quality checks on generated LaTeX files.

This module is the programmatic equivalent of the root-level `verify.py`
script.  It is called automatically inside the pipeline (latex_builder.py)
so that the user NEVER has to run a separate verification step.

Checks performed:
  1. No Persian / Arabic characters (\u0600–\u06FF) in French/English .tex
  2. Required LaTeX macros present (\\CompanyName, \\RecipientName, etc.)

If any check fails a QualityError is raised BEFORE LaTeX compilation so the
pipeline fails fast without wasting compilation time on bad output.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.core.logger import logger

# ─── Patterns ─────────────────────────────────────────────────────────────────

_PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")

# Placeholder tokens that must NOT remain in a filled template
# We look for common placeholder patterns: [bracketed], <angle>, XXX, ???, or empty definitions in \newcommand
_UNFILLED_RE = re.compile(
    r"\\(CompanyName|PositionTitle|RecipientName|WhyThisCompany|Variant)\s*\{"
    r"(?:[Xx<\?\[\]]{2,30}|\[[^\]]+\]|<[^>]+>)"
    r"\}"
)


class QualityError(ValueError):
    """Raised when a generated .tex file fails a quality check."""


# ─── Public API ───────────────────────────────────────────────────────────────

def verify_tex_files(*paths: Path) -> None:
    """
    Run all quality checks on one or more .tex file paths.

    Raises
    ------
    QualityError
        Describing all issues found, across all files.
        Raised BEFORE LaTeX compilation so nothing is compiled if checks fail.
    """
    all_issues: list[str] = []

    for path in paths:
        if not path.exists():
            all_issues.append(f"{path.name}: file not found")
            continue

        issues = _check_file(path)
        if issues:
            all_issues.extend(f"{path.name}: {msg}" for msg in issues)
        else:
            logger.debug(f"Quality Guard — OK: {path.name}")

    if all_issues:
        bullet_list = "\n  ".join(all_issues)
        raise QualityError(
            f"Quality Guard failed ({len(all_issues)} issue(s)):\n  {bullet_list}"
        )

    logger.info(f"Quality Guard — all {len(paths)} file(s) passed.")


def verify_tex_files_warn(*paths: Path) -> list[str]:
    """
    Same as verify_tex_files() but returns issues as a list instead of raising.
    Useful for non-blocking reports (e.g. logging a summary without aborting).
    """
    all_issues: list[str] = []
    for path in paths:
        if path.exists():
            issues = _check_file(path)
            all_issues.extend(f"{path.name}: {msg}" for msg in issues)
    return all_issues


# ─── Internal checks ──────────────────────────────────────────────────────────

def _check_file(path: Path) -> list[str]:
    """Return a list of issue strings for a single file (empty == clean)."""
    issues: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"cannot read file: {exc}"]

    # Check 1 — Persian / Arabic characters
    for i, line in enumerate(text.splitlines(), 1):
        if _PERSIAN_RE.search(line):
            issues.append(
                f"line {i}: Persian/Arabic characters detected — "
                f"'{line.strip()[:80]}'"
            )

    # Check 2 — Unfilled template placeholders
    for match in _UNFILLED_RE.finditer(text):
        issues.append(
            f"unfilled placeholder: {match.group(0)!r}"
        )

    return issues
