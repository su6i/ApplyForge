"""
roles.py — Roles Registry loader (single source of truth for CV tracks).

Reads ``config/roles.yaml`` and exposes every role-derived map the pipeline
needs, replacing the role dictionaries that used to be hardcoded in
``role_classifier``, ``resume_loader``, ``service``, ``latex_builder`` and
``altacv_renderer``.

Canonical role keys: python / ai / devops / devops_alternance / phd / support.
There are no aliases — a role is identified only by its canonical key (matching
is case-insensitive and treats ``-`` and ``_`` as equivalent).

To add a role: edit ``config/roles.yaml`` directly, or call
:func:`scaffold_role` to auto-generate a template stub + registry entry.
"""
from __future__ import annotations

import functools
import shutil
from pathlib import Path
from typing import Any

import yaml

from src.core.logger import logger
from src.core.settings import REPO_ROOT

REGISTRY_PATH: Path = REPO_ROOT / "config" / "roles.yaml"
TEMPLATES_ROOT: Path = REPO_ROOT / "templates"


# ─── Loading ──────────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    """Parsed registry (cached). Call :func:`reload` after editing the file."""
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Roles registry not found: {REGISTRY_PATH}")
    with REGISTRY_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not data.get("roles"):
        raise ValueError(f"No roles defined in {REGISTRY_PATH}")
    return data


def reload() -> None:
    """Drop the cached registry (use after the YAML file changes on disk)."""
    _data.cache_clear()
    _key_index.cache_clear()


def roles() -> dict[str, Any]:
    """Mapping of canonical role key → role definition dict."""
    return _data()["roles"]


def canonical_keys() -> list[str]:
    """Ordered list of canonical role keys (e.g. ['general','devops','ai','phd'])."""
    return list(roles().keys())


def default_role() -> str:
    """Fallback role used when classification is unparseable."""
    return _data().get("default_role", canonical_keys()[0])


# ─── Resolution ───────────────────────────────────────────────────────────────

def _norm(role: str) -> str:
    # Canonical keys use underscores (e.g. devops_alternance); accept hyphens too.
    return role.strip().lower().replace("-", "_")


@functools.lru_cache(maxsize=1)
def _key_index() -> dict[str, str]:
    """Normalised-key → canonical-key map (no aliases, just case/separator folding)."""
    return {_norm(key): key for key in roles()}


def resolve(role: str | None) -> str | None:
    """Map an input to its canonical role key (case/separator-insensitive).

    Returns ``None`` if the input is not a known canonical role.
    """
    if not role:
        return None
    return _key_index().get(_norm(role))


def is_valid(role: str | None) -> bool:
    """True if ``role`` is a known canonical role."""
    return resolve(role) is not None


def require(role: str | None) -> str:
    """Resolve to a canonical key or raise ``ValueError`` listing valid roles."""
    key = resolve(role)
    if key is None:
        raise ValueError(
            f"Unknown role {role!r}. Available: {', '.join(canonical_keys())}"
        )
    return key


def _entry(role: str | None) -> dict[str, Any]:
    """Role definition for ``role`` (falls back to the default role)."""
    key = resolve(role) or default_role()
    return roles()[key]


# ─── Derived maps ─────────────────────────────────────────────────────────────

def _title_fallback(role: str) -> str:
    return role.strip().replace("_", " ").replace("-", " ").title().replace(" ", "")


def label(role: str) -> str:
    """Canonical label used in generated filenames (e.g. 'AI', 'DevOps').

    Unknown strings fall back to a CamelCase rendering so arbitrary roles still
    produce a stable filename component.
    """
    key = resolve(role)
    if key is not None:
        return roles()[key]["label"]
    return _title_fallback(role)


def description(role: str) -> str:
    """One-line role description used in the classifier prompt."""
    return " ".join(_entry(role).get("description", "").split())


def default_lang(role: str) -> str:
    """Default output language for a role ('fr' or 'en')."""
    return _entry(role).get("lang", "en")


def skill_order(role: str, default: list[str] | None = None) -> list[str]:
    """Ordered skill-category keys for a role (drives the renderer ordering)."""
    fallback = default or ["ai_ml", "mlops_devops", "networks_support", "data"]
    return _entry(role).get("skill_order", fallback)


def cv_template(role: str) -> tuple[str, str]:
    """``(template_folder, filename)`` for the role's primary CV template."""
    cv = _entry(role)["cv"]
    return cv["folder"], cv["file"]


def lato_template(role: str) -> tuple[str | None, str]:
    """``(filename, stem)`` for the role's lato template (used as a fallback hint)."""
    lt = _entry(role).get("lato", {})
    return lt.get("file"), lt.get("stem", "AI_Data")


def spontaneous(role: str) -> tuple[str, str, str]:
    """``(folder, filename, default_lang)`` for the role's spontaneous template."""
    sp = require(role)
    s = roles()[sp]["spontaneous"]
    return s["folder"], s["file"], s.get("lang", "fr")


def variant_for(role: str, lang: str) -> str:
    """Cover-letter ``\\Variant`` value for a role + output language."""
    v = _entry(role).get("variant", {})
    lang = (lang or "fr").strip().lower()
    return v.get(lang) or v.get("fr") or "ai"


# ─── Classifier helpers ───────────────────────────────────────────────────────

def classifier_keys() -> list[str]:
    """Valid one-word outputs the classifier may emit."""
    return canonical_keys()


def classifier_descriptions(indent: str = "  ") -> str:
    """Formatted ``key → description`` block for injection into the LLM prompt."""
    width = max(len(k) for k in canonical_keys())
    lines = [
        f"{indent}{key.ljust(width)}  → {description(key)}"
        for key in canonical_keys()
    ]
    return "\n".join(lines)


# ─── Auto-scaffold ────────────────────────────────────────────────────────────

def scaffold_role(
    role: str,
    *,
    base: str | None = None,
    label_override: str | None = None,
    lang: str | None = None,
    registry_path: Path | None = None,
    templates_root: Path | None = None,
) -> str:
    """Register a new role by cloning an existing one's template + YAML entry.

    Copies the ``base`` role's CV template to a new ``CV_<Label>_<lang>.tex`` stub
    (with a tagline placeholder comment) and appends a registry entry derived
    from ``base``. Returns the new canonical key. No-op if the role already
    exists.

    ``registry_path`` / ``templates_root`` are overridable for testing; they
    default to the real registry and templates tree.
    """
    registry_path = registry_path or REGISTRY_PATH
    templates_root = templates_root or TEMPLATES_ROOT

    with registry_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    role_defs: dict[str, Any] = data.get("roles", {})

    # Match against canonical keys only (no aliases).
    local_index = {_norm(key): key for key in role_defs}
    existing = local_index.get(_norm(role))
    if existing is not None:
        logger.debug(f"scaffold_role: {role!r} already exists as {existing!r}; no-op")
        return existing

    base_key = base or data.get("default_role") or next(iter(role_defs))
    if base_key not in role_defs:
        raise ValueError(f"Base role {base_key!r} not found in {registry_path}")
    base_defn = role_defs[base_key]

    new_key = _norm(role).replace("-", "_")
    new_label = label_override or _title_fallback(role)
    new_lang = (lang or base_defn.get("lang", "fr")).strip().lower()

    # Clone the base CV template into a new stub with a placeholder comment.
    base_cv = base_defn["cv"]
    src_tex = templates_root / base_cv["folder"] / base_cv["file"]
    if not src_tex.exists():
        raise FileNotFoundError(f"Base template not found for scaffold: {src_tex}")
    new_file = f"CV_{new_label}_{new_lang}.tex"
    dest_tex = templates_root / base_cv["folder"] / new_file
    shutil.copy2(src_tex, dest_tex)
    placeholder = (
        f"% AUTO-SCAFFOLD: stub for role '{new_key}' (cloned from '{base_key}').\n"
        f"% TODO: replace the tagline/title below with {new_label}-specific content.\n"
    )
    dest_tex.write_text(placeholder + dest_tex.read_text(encoding="utf-8"), encoding="utf-8")

    # Append a registry entry derived from the base role.
    role_defs[new_key] = {
        "label": new_label,
        "description": f"Auto-scaffolded role {new_label} (cloned from {base_key}).",
        "lang": new_lang,
        "skill_order": list(base_defn.get("skill_order", [])),
        "cv": {"folder": base_cv["folder"], "file": new_file},
        "lato": dict(base_defn.get("lato", {})),
        "spontaneous": {"folder": base_cv["folder"], "file": new_file, "lang": new_lang},
        "variant": dict(base_defn.get("variant", {"fr": "it", "en": "python"})),
    }
    data["roles"] = role_defs

    header = (
        "# ApplyForge — Roles Registry (single source of truth for CV tracks)\n"
        "# Auto-managed: edit by hand or via src.core.roles.scaffold_role.\n\n"
    )
    with registry_path.open("w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, default_flow_style=False)

    if registry_path == REGISTRY_PATH:
        reload()
    logger.info(f"Scaffolded new role {new_key!r} (label={new_label!r}, stub={new_file})")
    return new_key
