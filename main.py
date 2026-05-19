"""
main.py — Entry point for the CV automation system.

Modes:
    uv run main.py bot                        → Start Telegram bot (recommended)
    uv run main.py apply <url> [--template] [--lang auto|<language>]   → Generate application from terminal
    uv run main.py spontaneous <role> [--city <city>] [--lang <language>] → Candidature spontanée (no LLM)
    uv run main.py preview [--template] [--lang <language>] [--no-localize-preview] → Preview CV with full profile data
    uv run main.py init-profile [--cv path]   → Parse LaTeX CV into resume_profile.json
    uv run main.py test                       → Sanity-check settings

Spontaneous roles: ai, ai-en, mlops, mlops-en, devops, devops-alternance, phd, polyvalent

    1. cp .env.example .env  (fill in OPENAI_API_KEY)
    2. uv run main.py init-profile
    3. uv run main.py apply <job_url> --template altacv

Must be run from the repository root.
"""
from __future__ import annotations

import sys


def cmd_bot() -> None:
    """Start the Telegram bot."""
    from src.bot.bot import CVBot
    CVBot().run()


def cmd_apply(
    url: str,
    template: str = "altacv",
    color: str = "",
    output_language: str = "auto",
    enable_fallback: bool = True,
) -> None:
    """
    Generate a tailored application from the terminal (no Telegram).
    
    If LLM translation fails and enable_fallback=True, offers offline dictionary fallback.
    """
    from src.pipeline.service import ApplicationService

    service = ApplicationService()
    bundle, error_msg, used_fallback = service.generate_with_llm_fallback(
        job_url=url,
        template=template,
        color=color,
        output_language=output_language,
        enable_fallback=enable_fallback,
    )
    
    # If LLM failed but fallback not enabled, try asking user interactively
    if bundle is None and error_msg and enable_fallback is False:
        print(f"\n⚠️  LLM-based generation failed: {error_msg}\n")
        print("Would you like to try offline dictionary-based generation? [y/N]")
        try:
            response = input().strip().lower()
            if response in ("y", "yes"):
                print("Attempting offline translation...")
                bundle, error_msg, used_fallback = service.generate_with_llm_fallback(
                    job_url=url,
                    template=template,
                    color=color,
                    output_language=output_language,
                    enable_fallback=True,
                )
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(1)
    
    if bundle is None:
        print(f"\n❌  Generation failed: {error_msg}")
        sys.exit(1)
    
    # Success
    status = "(fallback: offline dictionary)" if used_fallback else "(LLM)"
    print(f"\n✅  Application bundle generated {status}:")
    print(f"   CV          : {bundle.cv_pdf}")
    print(f"   Cover letter: {bundle.cl_pdf}")
    print(f"   Folder      : {bundle.output_dir}\n")


def cmd_spontaneous(
    role: str,
    city: str = "",
    language: str = "",
) -> None:
    """
    Generate a spontaneous application CV (candidature spontanée) — no LLM.
    Uses the pre-written static template for the given role.
    """
    from src.pipeline.service import ApplicationService

    service = ApplicationService()
    try:
        bundle = service.generate_spontaneous(role=role, city=city, language=language)
    except ValueError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    print(f"✅ Spontaneous CV ready: {bundle.cv_pdf}")
    print(f"   Folder: {bundle.output_dir}")


def cmd_preview(
    template: str = "altacv",
    role: str = "it",
    color: str = "",
    output_language: str = "fr",
    localize_preview: bool = True,
) -> None:
    """Generate a preview bundle reflecting the full profile data."""
    from src.pipeline.service import ApplicationService

    service = ApplicationService()
    bundle = service.preview(
        template=template,
        role=role,
        color=color,
        output_language=output_language,
        localize_preview=localize_preview,
    )
    print("\n✅  Preview bundle generated:")
    print(f"   CV    : {bundle.cv_pdf}")
    print(f"   Folder: {bundle.output_dir}\n")

def cmd_init_profile(cv_path: str | None = None) -> None:
    """
    Parse the primary LaTeX CV into data/resume_profile.json.

    Uses the LLM to extract structured data (skills, experience, projects, etc.)
    from the .tex source and writes the result as JSON.  Run this once after
    creating or updating your CV templates.

    Optional:
        --cv  path/to/CV.tex|.pdf|.jpg   (default: templates/lato/CV_AI_Data_Lato.tex)
                Supported: .tex, .pdf, .jpg, .jpeg, .png, .webp
    """
    from pathlib import Path
    from src.pipeline.resume_parser import parse_cv_to_profile, PROFILE_PATH

    cv_tex = Path(cv_path) if cv_path else None
    print("Parsing CV into resume_profile.json …")
    profile = parse_cv_to_profile(cv_tex)
    print(f"\n\u2705  Profile saved to {PROFILE_PATH}")
    print(f"   Name  : {profile.get('identity', {}).get('name', 'N/A')}")
    print(f"   Skills: {sum(len(v) for v in profile.get('skills', {}).values())} entries")
    print(f"   Exp   : {len(profile.get('experience', []))} positions")
    print(f"   Proj  : {len(profile.get('projects', []))} projects\n")


def cmd_test() -> None:
    """Print current configuration and check dependencies."""
    from src.core.settings import (
        COVER_LETTERS_DIR,
        LLM_MODEL,
        OPENAI_API_KEY,
        TELEGRAM_BOT_TOKEN,
        TEMPLATES_LATO,
        TEMPLATES_SHARED,
        REPO_ROOT,
    )

    profile_path = REPO_ROOT / "data" / "resume_profile.json"

    print("\n── Settings ────────────────────────────────────────────────")
    print(f"  LLM model         : {LLM_MODEL}")
    print(f"  OpenAI key set    : {'yes' if OPENAI_API_KEY else 'NO — set OPENAI_API_KEY in .env'}")
    print(f"  Telegram token set: {'yes' if TELEGRAM_BOT_TOKEN else 'NO — set TELEGRAM_BOT_TOKEN in .env'}")
    print(f"  templates/lato    : {'\u2713' if TEMPLATES_LATO.exists() else '\u2717  NOT FOUND'} ({TEMPLATES_LATO})")
    print(f"  templates/shared  : {'\u2713' if TEMPLATES_SHARED.exists() else '\u2717  NOT FOUND'} ({TEMPLATES_SHARED})")
    print(f"  cover_letters/    : {'\u2713' if COVER_LETTERS_DIR.exists() else '\u2717  NOT FOUND'} ({COVER_LETTERS_DIR})")
    print(f"  resume_profile    : {'\u2713' if profile_path.exists() else '\u2717  NOT FOUND — run: python main.py init-profile'} ({profile_path})")

    try:
        import subprocess
        r = subprocess.run(["pdflatex", "--version"], capture_output=True)
        print(f"  pdflatex          : {'✓' if r.returncode == 0 else '✗  not found'}")
        r = subprocess.run(["xelatex", "--version"], capture_output=True)
        print(f"  xelatex           : {'✓' if r.returncode == 0 else '✗  not found'}")
    except FileNotFoundError:
        print("  LaTeX             : ✗  pdflatex/xelatex not in PATH")

    print()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return

    command = args[0]

    if command == "bot":
        cmd_bot()

    elif command == "apply":
        if len(args) < 2:
            print("Usage: uv run main.py apply <job-url> [--template altacv|lato] [--lang auto|<language>] [--no-fallback]")
            sys.exit(1)
            
        url = args[1]
        template = "altacv"
        if "--template" in args:
            idx = args.index("--template")
            if idx + 1 < len(args):
                template = args[idx + 1]
                
        color = ""
        if "--color" in args:
            idx = args.index("--color")
            if idx + 1 < len(args):
                color = args[idx + 1]

        output_language = "auto"
        if "--lang" in args:
            idx = args.index("--lang")
            if idx + 1 < len(args):
                output_language = args[idx + 1].strip().lower()
                if not output_language:
                    print("Invalid --lang value. Use: auto or any language code/name (e.g., fr, en, es, de, it, fa)")
                    sys.exit(1)
        
        enable_fallback = "--no-fallback" not in args
                
        cmd_apply(url, template, color, output_language, enable_fallback)

    elif command == "spontaneous":
        if len(args) < 2:
            print("Usage: uv run main.py spontaneous <role> [--city <city>] [--lang fr|en]")
            print("Roles: ai, ai-en, mlops, mlops-en, devops, devops-alternance, phd, polyvalent")
            sys.exit(1)

        role = args[1]
        city = ""
        if "--city" in args:
            idx = args.index("--city")
            if idx + 1 < len(args):
                city = args[idx + 1]
        language = ""
        if "--lang" in args:
            idx = args.index("--lang")
            if idx + 1 < len(args):
                language = args[idx + 1].strip().lower()

        cmd_spontaneous(role, city, language)

    elif command in ("init-profile", "init_profile"):
        # Optional: --cv path/to/file.tex
        cv_path = None
        if "--cv" in args:
            idx = args.index("--cv")
            if idx + 1 < len(args):
                cv_path = args[idx + 1]
        cmd_init_profile(cv_path)

    elif command == "preview":
        template = "altacv"
        if "--template" in args:
            idx = args.index("--template")
            if idx + 1 < len(args):
                template = args[idx + 1]
        
        role = "it"
        if "--role" in args:
            idx = args.index("--role")
            if idx + 1 < len(args):
                role = args[idx + 1]
                
        color = ""
        if "--color" in args:
            idx = args.index("--color")
            if idx + 1 < len(args):
                color = args[idx + 1]

        output_language = "fr"
        if "--lang" in args:
            idx = args.index("--lang")
            if idx + 1 < len(args):
                output_language = args[idx + 1].strip().lower()
                if not output_language:
                    print("Invalid --lang value. Use any language code/name (e.g., fr, en, es, de, it, fa)")
                    sys.exit(1)

        localize_preview = "--no-localize-preview" not in args
                
        cmd_preview(template, role, color, output_language, localize_preview)

    elif command == "test":
        cmd_test()

    else:
        print(f"Unknown command: {command!r}")
        print("Available commands: bot, apply <url>, spontaneous <role>, preview, test")
        sys.exit(1)


if __name__ == "__main__":
    main()
