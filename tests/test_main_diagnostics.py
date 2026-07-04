"""
test_main_diagnostics.py — `uv run main.py test` must not give false negatives.

Covers two bugs:
  1. It only checked OPENAI_API_KEY, so a DeepSeek-only setup (LLM_MODEL=deepseek-chat,
     DEEPSEEK_API_KEY set) reported "NO" even though the app works fine.
  2. It only checked the legacy data/resume_profile.json, so a vault-based install with
     role source profiles ({slug}-CV_<Role>_source.json in DATA_DIR) reported "NOT FOUND"
     even though profiles exist.

Runnable two ways (pytest is optional in this repo):
    .venv/bin/python tests/test_main_diagnostics.py     # plain-python self-runner
    pytest tests/test_main_diagnostics.py                 # if pytest is installed
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly (python tests/test_main_diagnostics.py) from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


def test_llm_status_prefers_deepseek_when_both_keys_set():
    # Mirrors src/core/llm_factory.py: DeepSeek wins if its key is set, regardless of model name.
    status = main._llm_status(
        model="deepseek-chat", deepseek_key="dk-x", openai_key="oa-y", gemini_key=""
    )
    assert status["provider"] == "DeepSeek"
    assert status["key_ok"] is True


def test_llm_status_falls_back_to_openai():
    status = main._llm_status(
        model="gpt-4o-mini", deepseek_key="", openai_key="oa-y", gemini_key=""
    )
    assert status["provider"] == "OpenAI"
    assert status["key_ok"] is True


def test_llm_status_no_key_is_a_real_failure():
    status = main._llm_status(model="deepseek-chat", deepseek_key="", openai_key="", gemini_key="")
    assert status["key_ok"] is False


def test_profile_status_checks_vault_role_sources_not_legacy_path(tmp_path):
    def fake_path(role: str, lang: str = "en") -> Path:
        return tmp_path / f"cv-owner-CV_{role.capitalize()}_source.json"

    (tmp_path / "cv-owner-CV_Python_source.json").write_text("{}", encoding="utf-8")

    status = main._profile_status(roles=["python", "ai"], path_fn=fake_path)
    assert status == {"python": True, "ai": False}


def _run_all() -> int:
    import inspect
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in tests:
        try:
            if "tmp_path" in inspect.signature(fn).parameters:
                import tempfile
                with tempfile.TemporaryDirectory() as tmp:
                    fn(Path(tmp))
            else:
                fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
