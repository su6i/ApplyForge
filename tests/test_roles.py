"""
test_roles.py — Roles Registry contract tests.

Runnable two ways (pytest is optional in this repo):
    .venv/bin/python tests/test_roles.py     # plain-python self-runner
    pytest tests/test_roles.py               # if pytest is installed
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Allow running directly (python tests/test_roles.py) from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core import roles as r

CANONICAL = ["python", "polyvalent", "ai", "devops", "devops_alternance", "phd", "support"]


def test_canonical_keys():
    assert r.canonical_keys() == CANONICAL


def test_default_role():
    assert r.default_role() == "python"


def test_resolve_is_canonical_only():
    # Exact canonical keys resolve.
    for key in CANONICAL:
        assert r.resolve(key) == key
    # Case / separator folding (devops-alternance == devops_alternance).
    assert r.resolve("AI") == "ai"
    assert r.resolve("PhD") == "phd"
    assert r.resolve("devops-alternance") == "devops_alternance"
    assert r.resolve("DEVOPS_ALTERNANCE") == "devops_alternance"
    # polyvalent is a real canonical role (kept for reuse).
    assert r.resolve("polyvalent") == "polyvalent"
    # No aliases: legacy / fuzzy names do NOT resolve.
    assert r.resolve("it") is None
    assert r.resolve("mlops") is None
    assert r.resolve("") is None
    assert r.resolve(None) is None


def test_is_valid_and_require():
    assert r.is_valid("support") is True
    assert r.is_valid("it") is False
    assert r.require("devops-alternance") == "devops_alternance"
    try:
        r.require("it")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("require() should raise on unknown role")


def test_label():
    assert r.label("python") == "Python"
    assert r.label("ai") == "AI"
    assert r.label("devops") == "DevOps"
    assert r.label("devops_alternance") == "DevOpsAlternance"
    assert r.label("phd") == "PhD"
    assert r.label("support") == "Support"
    # Unknown strings get a stable CamelCase fallback (filename-safe).
    assert r.label("cloud_native") == "CloudNative"


def test_cv_templates_exist():
    templates = Path(r.TEMPLATES_ROOT)
    for key in CANONICAL:
        folder, filename = r.cv_template(key)
        assert (templates / folder / filename).exists(), f"missing CV template for {key}"


def test_spontaneous():
    folder, filename, lang = r.spontaneous("ai")
    assert (folder, filename, lang) == ("altacv", "CV_AI_fr.tex", "fr")
    folder, filename, lang = r.spontaneous("support")
    assert filename == "CV_Support_fr.tex"
    folder, filename, lang = r.spontaneous("phd")
    assert folder == "lato" and filename == "CV_PhD_en.tex" and lang == "en"


def test_cv_template_filenames_follow_scheme():
    # CV_<Label>_<lang>.tex convention.
    assert r.cv_template("ai") == ("altacv", "CV_AI_fr.tex")
    assert r.cv_template("devops_alternance") == ("altacv", "CV_DevOpsAlternance_fr.tex")
    assert r.cv_template("support") == ("lato", "CV_Support_fr.tex")
    assert r.cv_template("python") == ("altacv", "CV_Python_fr.tex")


def test_variant_for():
    assert r.variant_for("ai", "fr") == "ai"
    assert r.variant_for("ai", "en") == "ai"
    assert r.variant_for("support", "fr") == "it"
    assert r.variant_for("devops", "en") == "python"
    assert r.variant_for("python", "fr") == "it"


def test_skill_order():
    assert r.skill_order("support")[0] == "networks_support"
    assert r.skill_order("devops")[0] == "mlops_devops"
    assert r.skill_order("ai")[0] == "ai_ml"


def test_classifier_helpers():
    assert set(r.classifier_keys()) == set(CANONICAL)
    block = r.classifier_descriptions()
    for key in CANONICAL:
        assert key in block


def test_scaffold_role_isolated():
    """scaffold_role appends a registry entry + clones a template stub."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        templates = tmp_path / "templates" / "altacv"
        templates.mkdir(parents=True)
        base_tex = templates / "CV_Base_fr.tex"
        base_tex.write_text(
            "\\documentclass{article}\n\\begin{document}base\\end{document}\n",
            encoding="utf-8",
        )
        registry = tmp_path / "roles.yaml"
        registry.write_text(
            "default_role: python\n"
            "roles:\n"
            "  python:\n"
            "    label: Python\n"
            "    description: base role\n"
            "    lang: fr\n"
            "    skill_order: [ai_ml, data]\n"
            "    cv: {folder: altacv, file: CV_Base_fr.tex}\n"
            "    lato: {file: CV_Base_Lato.tex, stem: Base}\n"
            "    spontaneous: {folder: altacv, file: CV_Base_fr.tex, lang: fr}\n"
            "    variant: {fr: it, en: python}\n",
            encoding="utf-8",
        )

        # Existing role is a no-op.
        assert r.scaffold_role(
            "python", base="python",
            registry_path=registry, templates_root=tmp_path / "templates",
        ) == "python"

        # New role gets registered + a stub template created.
        new_key = r.scaffold_role(
            "cloud", base="python",
            registry_path=registry, templates_root=tmp_path / "templates",
        )
        assert new_key == "cloud"

        import yaml
        data = yaml.safe_load(registry.read_text(encoding="utf-8"))
        assert "cloud" in data["roles"]
        assert "aliases" not in data["roles"]["cloud"]  # no alias machinery
        assert data["roles"]["cloud"]["label"] == "Cloud"
        stub = data["roles"]["cloud"]["cv"]["file"]
        assert (tmp_path / "templates" / "altacv" / stub).exists()


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
