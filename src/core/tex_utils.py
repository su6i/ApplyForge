"""
tex_utils.py — Shared LaTeX helper utilities used across pipeline modules.

Centralised here to avoid duplication between latex_builder.py and cv_renderer.py.
"""
from __future__ import annotations

import re

# Unicode characters that have a LaTeX-safe replacement
_UNICODE_REPLACEMENTS: dict[str, str] = {
    " ": " ",   # non-breaking space
    " ": " ",   # narrow no-break space (e.g. French "80 000")
    " ": " ",   # thin space
    "‘": "'",   # left single quotation mark
    "’": "'",   # right single quotation mark
    "“": "``",  # left double quotation mark
    "”": "''",  # right double quotation mark
    "–": "--",  # en dash
    "—": "---", # em dash
    "…": "...", # ellipsis
}


def latex_escape(text: str) -> str:
    """Escape characters that have special meaning in LaTeX."""
    # Replace known Unicode chars that pdflatex cannot handle
    for char, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(char, replacement)

    # Order matters — backslash must be first
    escapes = [
        ("\\", r"\textbackslash{}"),
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\^{}"),
    ]
    for char, replacement in escapes:
        text = text.replace(char, replacement)
    return text


def slugify(text: str, max_words: int = 4) -> str:
    """Convert text to a filesystem-safe CamelCase slug."""
    words = re.sub(r"[^a-zA-Z0-9\s]", "", text).split()[:max_words]
    return "".join(w.capitalize() for w in words) or "Unknown"


def itemize(items: list[str], indent: str = "    ") -> str:
    """Render a list of strings as LaTeX \\item lines (without begin/end)."""
    return "\n".join(
        f"{indent}    \\item {latex_escape(item)}" for item in items
    )
