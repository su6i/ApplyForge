"""
latex_builder.py — Compile a tailored CV + cover letter from LaTeX templates.

Flow per application:
    1. Select CV template  (based on role: ai / it / phd)
    2. Select CL template  (based on language: fr / en)
    3. Create output folder:  Applied/YYYY-MM_CompanySlug_RoleSlug/
    4. Copy CV .tex + dependencies into output folder, compile → PDF
    5. Instantiate CL template (substitute \newcommand values), compile → PDF
    6. Return (cv_pdf_path, cl_pdf_path)

Compilation:
    CV uses pdflatex (needs lato_macros.tex + ../shared/personal_data.tex).
    Cover letter uses xelatex (fontspec / Times New Roman).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from src.core.logger import logger
from src.core.quality_guard import verify_tex_files
from src.core.settings import (
    APPLIED_DIR,
    COVER_LETTERS_DIR,
    CV_OWNER_SLUG,
    TEMPLATES_LATO,
    TEMPLATES_SHARED,
)
from src.core.tex_utils import latex_escape, slugify
from src.pipeline import altacv_renderer
from src.pipeline.content_tailor import TailoredContent
from src.pipeline.job_scraper import JobPosting
from src.pipeline.role_classifier import RoleType


# ─── Template mapping ─────────────────────────────────────────────────────────

# Canonical source filenames in templates/lato/ (used by _find_template_file as hint)
_CV_TEMPLATES: dict[RoleType, str] = {
    "ai":  "CV_AI_Data_Lato.tex",
    "it":  "CV_IT_Infra_Lato.tex",
    "phd": "CV_PhD_Lato.tex",
}

# Spontaneous application templates: role_key → (template_folder, filename, default_lang)
_SPONTANEOUS_MAP: dict[str, tuple[str, str, str]] = {
    "devops-alternance": ("altacv", "CV_DevOps_Alternance_fr.tex", "fr"),
    "devops":            ("altacv", "CV_DevOps_Alternance_fr.tex", "fr"),
    "ai":                ("altacv", "CV_AI_MLOps_fr.tex",          "fr"),
    "ai-en":             ("altacv", "CV_AI_MLOps_en.tex",          "en"),
    "mlops":             ("altacv", "CV_AI_MLOps_fr.tex",          "fr"),
    "mlops-en":          ("altacv", "CV_AI_MLOps_en.tex",          "en"),
    "phd":               ("lato",   "CV_PhD_Research_en.tex",      "en"),
    "polyvalent":        ("altacv", "CV_Polyvalent_fr.tex",         "fr"),
}

_CL_TEMPLATES: dict[str, str] = {
    "fr": "Lettre_de_Motivation_Template.tex",
    "en": "Cover_Letter_Template_English.tex",
}

_ROLE_LABEL_MAP = {
    "ai": "AI",
    "it": "IT",
    "phd": "PhD",
    "python": "Python",
    "devops": "DevOps",
}


def _canonical_role_label(role: str) -> str:
    normalized = role.strip().lower().replace("_", "-")
    if normalized in _ROLE_LABEL_MAP:
        return _ROLE_LABEL_MAP[normalized]
    return role.strip().replace("_", " ").replace("-", " ").title().replace(" ", "")


@dataclass
class ApplicationBundle:
    output_dir: Path
    cv_pdf: Path
    cl_pdf: Path | None = None


# ─── Public API ───────────────────────────────────────────────────────────────

def build(
    role: RoleType,
    content: TailoredContent,
    profile: dict | None = None,
    template: str = "altacv",
    job_posting: JobPosting | None = None,
    job_url: str = "",
) -> ApplicationBundle:
    """
    Compile a tailored CV + cover letter for one application.

    Parameters
    ----------
    role    : Classified role type (ai / it / phd).
    content : LLM-tailored content including selected experience/projects.
    profile : Full candidate profile dict (from resume_profile.json).
              Used by cv_renderer to generate the CV dynamically.
              If None, falls back to a plain template copy.

    Returns
    -------
    ApplicationBundle with paths to both PDFs.
    """
    output_dir = _create_output_dir(content, role)
    logger.info(f"Application output dir: {output_dir}")

    cv_pdf = _build_cv(role, content, output_dir, profile, template)
    cl_pdf = _build_cover_letter(role, content, output_dir)

    if job_posting and job_url:
        _save_job_posting_snapshot(
            content=content,
            output_dir=output_dir,
            job_posting=job_posting,
            job_url=job_url,
            role=role,
        )

    return ApplicationBundle(output_dir=output_dir, cv_pdf=cv_pdf, cl_pdf=cl_pdf)


# ─── Spontaneous application ──────────────────────────────────────────────────

def build_spontaneous(
    role_key: str,
    city: str = "",
    language: str = "",
) -> ApplicationBundle:
    """
    Compile a spontaneous CV from a pre-written static template (no LLM).

    Parameters
    ----------
    role_key : Key from _SPONTANEOUS_MAP (e.g., "ai", "phd", "devops-alternance").
    city     : Job location hint for city selection (e.g., "montpellier", "grenoble").
               Empty string → defaults to Grenoble.
    language : Override output language. Empty → use template's default language.
    """
    if role_key not in _SPONTANEOUS_MAP:
        available = ", ".join(sorted(_SPONTANEOUS_MAP.keys()))
        raise ValueError(f"Unknown spontaneous role {role_key!r}. Available: {available}")

    from src.core.settings import REPO_ROOT
    template_folder, template_file, default_lang = _SPONTANEOUS_MAP[role_key]
    lang = (language or default_lang).strip().lower()

    src_tex = REPO_ROOT / "templates" / template_folder / template_file
    if not src_tex.exists():
        raise FileNotFoundError(f"Spontaneous template not found: {src_tex}")

    # Create output dir
    date_str = datetime.now().strftime("%Y-%m-%d")
    role_slug = role_key.replace("-", "_")
    folder_name = f"{date_str}_Spontannee_{role_slug}_{lang}"
    output_dir = APPLIED_DIR / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy template + dependencies into output dir
    _copy_deps(output_dir, template_folder)

    # Determine output filename
    role_label = _canonical_role_label(role_slug)
    cv_tex_name = f"{CV_OWNER_SLUG}-CV_{role_label}_{lang}.tex"
    cv_tex_path = output_dir / cv_tex_name
    shutil.copy2(src_tex, cv_tex_path)

    # personal_data.tex uses \newcommand which conflicts with \providecommand already
    # defined in the static template. Strip \providecommand lines so personal_data.tex
    # can define the macros cleanly with \newcommand.
    _strip_providecommands(cv_tex_path)

    # Inject location override
    _inject_location_override(cv_tex_path, job_location=city, language=lang)

    # Compile
    engine = "xelatex" if template_folder == "altacv" else "pdflatex"
    _run_latex(engine=engine, tex_file=cv_tex_name, work_dir=output_dir, runs=2)

    cv_pdf = cv_tex_path.with_suffix(".pdf")
    if not cv_pdf.exists():
        raise RuntimeError(f"LaTeX did not produce {cv_pdf}")

    logger.info(f"Spontaneous CV compiled: {cv_pdf}")
    return ApplicationBundle(output_dir=output_dir, cv_pdf=cv_pdf, cl_pdf=None)


# ─── CV compilation ───────────────────────────────────────────────────────────

def _build_cv(role: RoleType, content: TailoredContent, output_dir: Path, profile: dict | None, template: str = "altacv") -> Path:
    """
    Generate a tailored CV .tex via cv_renderer (or copy template if no profile),
    then compile with pdflatex. Returns path to the generated PDF.
    """
    # Always copy dependencies into output dir
    _copy_deps(output_dir, template)

    # Find the best .tex template in the output directory
    template_filename = _find_template_file(output_dir, role, template)
    lang_tag = (content.language or "en").lower()
    role_label = _canonical_role_label(str(role))
    cv_tex_name = f"{CV_OWNER_SLUG}-CV_{role_label}_{lang_tag}.tex"
    cv_tex_path = output_dir / cv_tex_name

    if profile:
        # Dynamic generation: CV is tailored per job
        logger.info(f"Generating tailored CV from profile + LLM selections (template: {template})…")
        if template == "lato":
            from src.pipeline import cv_renderer
            cv_tex_content = cv_renderer.render(profile, content)
        else:
            from src.pipeline import altacv_renderer
            cv_tex_content = altacv_renderer.render(profile, content)
        cv_tex_path.write_text(cv_tex_content, encoding="utf-8")
    else:
        # Fallback: copy the static template (we use the file we found)
        logger.warning(f"No profile loaded — falling back to static CV template: {template_filename}")
        src_tex = output_dir / template_filename
        if not src_tex.exists():
             raise FileNotFoundError(f"CV template not found: {src_tex}")
        shutil.copy2(src_tex, cv_tex_path)

    # Inject \cvlocation override based on job location (Occitanie → Montpellier, else Grenoble)
    _inject_cv_location(cv_tex_path, content)

    # Quality check before burning compile time
    verify_tex_files(cv_tex_path)

    # altacv uses xelatex (fontspec); lato/classic use pdflatex
    engine = "xelatex" if template == "altacv" else "pdflatex"
    _run_latex(engine=engine, tex_file=cv_tex_name, work_dir=output_dir, runs=2)

    cv_pdf = cv_tex_path.with_suffix(".pdf")
    if not cv_pdf.exists():
        raise RuntimeError(f"pdflatex did not produce {cv_pdf}")

    logger.info(f"CV compiled: {cv_pdf}")
    return cv_pdf


def _strip_providecommands(tex_path: Path) -> None:
    """
    Remove \\providecommand{\\cvXxx}{...} lines from a static template.

    Static templates define macro defaults with \\providecommand so they compile
    standalone. When personal_data.tex is present it tries \\newcommand for the
    same macros, causing "Command already defined" errors. Stripping the
    \\providecommand lines lets personal_data.tex own the definitions.
    """
    tex = tex_path.read_text(encoding="utf-8")
    tex = re.sub(
        r'^\\providecommand\{\\cv[A-Za-z]+\}\{[^}]*\}[ \t]*\n?',
        '',
        tex,
        flags=re.MULTILINE,
    )
    tex_path.write_text(tex, encoding="utf-8")


def _inject_location_override(tex_path: Path, job_location: str, language: str) -> None:
    """
    Inject \\renewcommand{\\cvlocation}{...} right after \\begin{document}.
    Occitanie region → Montpellier, everywhere else → Grenoble.
    """
    from src.core.location_utils import select_cv_city
    city = select_cv_city(job_location, language)
    override = f"\\renewcommand{{\\cvlocation}}{{{city}}}  % auto: {job_location or 'unknown'}\n"
    tex = tex_path.read_text(encoding="utf-8")
    if "\\begin{document}" not in tex:
        return
    tex = tex.replace("\\begin{document}", "\\begin{document}\n" + override, 1)
    tex_path.write_text(tex, encoding="utf-8")
    logger.debug(f"CV location set to {city!r} (job_location={job_location!r})")


def _inject_cv_location(tex_path: Path, content: TailoredContent) -> None:
    _inject_location_override(
        tex_path,
        job_location=getattr(content, "job_location", "") or "",
        language=str(getattr(content, "language", "fr") or "fr"),
    )


def _copy_deps(output_dir: Path, template: str = "altacv") -> None:
    """
    Copy all required .tex and .cls files from templates/ to the output dir.
    """
    if template == "lato":
        for f in TEMPLATES_LATO.glob("*.tex"):
            shutil.copy2(f, output_dir / f.name)
    else:
        # Check if it's a folder in templates/
        from src.core.settings import REPO_ROOT
        template_dir = REPO_ROOT / "templates" / template
        if template_dir.exists() and template_dir.is_dir():
             for f in template_dir.iterdir():
                if f.suffix in (".tex", ".cls", ".sty"):
                    shutil.copy2(f, output_dir / f.name)
        else:
            # Fallback to altacv
            from src.core.settings import TEMPLATES_ALTACV
            if TEMPLATES_ALTACV.exists():
                for f in TEMPLATES_ALTACV.iterdir():
                    if f.suffix in (".tex", ".cls"):
                        shutil.copy2(f, output_dir / f.name)

    # shared/ sibling
    shared_dest = output_dir.parent / "shared"
    shared_dest.mkdir(parents=True, exist_ok=True)
    for f in TEMPLATES_SHARED.glob("*.tex"):
        shutil.copy2(f, shared_dest / f.name)


# ─── Cover letter compilation ─────────────────────────────────────────────────

def _build_cover_letter(role: RoleType, content: TailoredContent, output_dir: Path) -> Path:
    """
    Instantiate the cover letter template (fill in \newcommand values),
    write it to output_dir, compile with xelatex.
    Returns path to the generated PDF.
    """
    cl_template_name = _CL_TEMPLATES.get(content.language, _CL_TEMPLATES["fr"])
    src_tex = COVER_LETTERS_DIR / cl_template_name
    if not src_tex.exists():
        raise FileNotFoundError(f"Cover letter template not found: {src_tex}")

    template_text = src_tex.read_text(encoding="utf-8")
    filled_text = _fill_cover_letter(template_text, content)

    role_label = _canonical_role_label(str(role))
    lang_tag = (content.language or "en").lower()
    cl_label = "LettreMotivation" if lang_tag == "fr" else "CoverLetter"
    cl_tex_name = f"{CV_OWNER_SLUG}-{cl_label}_{role_label}_{lang_tag}.tex"
    cl_tex_path = output_dir / cl_tex_name
    cl_tex_path.write_text(filled_text, encoding="utf-8")

    # Quality check: verify filled cover letter before compilation
    verify_tex_files(cl_tex_path)

    _run_latex(
        engine="xelatex",
        tex_file=cl_tex_name,
        work_dir=output_dir,
        runs=1,
    )

    cl_pdf = cl_tex_path.with_suffix(".pdf")
    if not cl_pdf.exists():
        raise RuntimeError(f"xelatex did not produce {cl_pdf}")

    logger.info(f"Cover letter compiled: {cl_pdf}")
    return cl_pdf


def _fill_cover_letter(template: str, content: TailoredContent) -> str:
    """
    Replace the placeholder \newcommand values in the template.

    We only replace between the opening brace and closing brace of the
    4 mandatory \newcommand definitions — leaving the rest of the file intact.
    """
    replacements = {
        r"(\\newcommand\{\\CompanyName\}\{)[^}]*(})": 
            rf"\g<1>{latex_escape(content.company_name)}\g<2>",
        r"(\\newcommand\{\\PositionTitle\}\{)[^}]*(})":
            rf"\g<1>{latex_escape(content.position_title)}\g<2>",
        r"(\\newcommand\{\\Variant\}\{)[^}]*(})":
            rf"\g<1>{content.variant}\g<2>",
        r"(\\newcommand\{\\WhyThisCompany\}\{)[^}]*(})":
            rf"\g<1>{latex_escape(content.why_this_company)}\g<2>",
    }
    result = template
    for pattern, repl in replacements.items():
        result = re.sub(pattern, repl, result, count=1)
    return result


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _create_output_dir(content: TailoredContent, role: str = "") -> Path:
    date_str     = datetime.now().strftime("%Y-%m-%d")
    company_slug = slugify(content.company_name, max_words=3)
    role_label   = _canonical_role_label(role) if role else "Gen"
    lang_tag     = (content.language or "en").lower()
    folder_name  = f"{date_str}_{company_slug}_{role_label}_{lang_tag}"

    output_dir = APPLIED_DIR / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _save_job_posting_snapshot(
    content: TailoredContent,
    output_dir: Path,
    job_posting: JobPosting,
    job_url: str,
    role: RoleType,
) -> None:
    applied_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lang_tag = (content.language or "en").lower()
    role_tag = _canonical_role_label(str(role))
    position_slug = slugify(content.position_title, max_words=4)

    md_name = f"JobPosting_{role_tag}_{position_slug}_{lang_tag}.md"
    tex_name = f"JobPosting_{role_tag}_{position_slug}_{lang_tag}.tex"

    md_path = output_dir / md_name
    tex_path = output_dir / tex_name

    posting_title = job_posting.title or content.position_title
    posting_body = (job_posting.body or "").strip()
    if not posting_body:
        return

    snapshot_meta = _extract_job_snapshot_metadata(
        posting_body=posting_body,
        posting_title=posting_title,
        company_name=content.company_name,
        position_title=content.position_title,
        role=role,
        output_language=lang_tag,
        applied_ts=applied_ts,
        job_url=job_url,
    )

    md_metadata_lines = [f"- {label}: {value}" for label, value in snapshot_meta.items() if value]

    markdown_lines = [
        "# Job Posting Snapshot",
        "",
        "## Metadata",
        "",
        *md_metadata_lines,
        "",
        "## Source Title",
        "",
        posting_title,
        "",
        "## Raw Posting Text",
        "",
        posting_body,
        "",
    ]
    md_path.write_text("\n".join(markdown_lines), encoding="utf-8")

    body_for_tex = "\n\n".join(
        latex_escape(chunk.strip())
        for chunk in posting_body.split("\n\n")
        if chunk.strip()
    )
    title_tex = latex_escape(posting_title)
    url_for_tex = job_url.replace("\\", "")

    tex_meta_lines: list[str] = []
    for label, value in snapshot_meta.items():
        if not value:
            continue
        if label == "Source URL":
            tex_meta_lines.append(f"\\textbf{{{latex_escape(label)}:}} \\url{{{url_for_tex}}}\\\\")
        else:
            tex_meta_lines.append(f"\\textbf{{{latex_escape(label)}:}} {latex_escape(value)}\\\\")
    tex_meta_block = "\n".join(tex_meta_lines)

    tex_content = f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage[margin=2cm]{{geometry}}
\\usepackage[T1]{{fontenc}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{hyperref}}
\\usepackage{{parskip}}

\\begin{{document}}
\\section*{{Job Posting Snapshot}}
{tex_meta_block}

\\section*{{Source Title}}
{title_tex}

\\section*{{Raw Posting Text}}
{body_for_tex}
\\end{{document}}
"""
    tex_path.write_text(tex_content, encoding="utf-8")

    try:
        _run_latex(engine="pdflatex", tex_file=tex_name, work_dir=output_dir, runs=1)
        _cleanup_snapshot_latex_artifacts(output_dir=output_dir, tex_stem=tex_path.stem)
    except Exception as exc:
        logger.warning(f"Could not compile job posting PDF snapshot: {exc}")


def _extract_job_snapshot_metadata(
    posting_body: str,
    posting_title: str,
    company_name: str,
    position_title: str,
    role: RoleType,
    output_language: str,
    applied_ts: str,
    job_url: str,
) -> dict[str, str]:
    text_lc = posting_body.lower()
    source_domain = urlparse(job_url).netloc

    location = ""
    location_match = re.search(r"(?:location|lieu|localisation)\s*[:\-]\s*([^\n]{2,120})", posting_body, flags=re.IGNORECASE)
    if location_match:
        location = location_match.group(1).strip()

    work_mode = ""
    if "hybrid" in text_lc:
        work_mode = "Hybrid"
    elif "remote" in text_lc or "t\u00e9l\u00e9travail" in text_lc:
        work_mode = "Remote"
    elif "on-site" in text_lc or "onsite" in text_lc or "sur site" in text_lc:
        work_mode = "On-site"

    employment_type = ""
    if re.search(r"\bfull[- ]?time\b|\bcdi\b", text_lc):
        employment_type = "Full-time"
    elif re.search(r"\bpart[- ]?time\b|\btemps partiel\b", text_lc):
        employment_type = "Part-time"
    elif re.search(r"\bintern(ship)?\b|\bstage\b", text_lc):
        employment_type = "Internship"
    elif re.search(r"\bcontract\b|\bccd\b|\bfreelance\b", text_lc):
        employment_type = "Contract"

    salary = ""
    salary_match = re.search(
        r"([$€£]\s?\d[\d\s,\.]*\s?(?:k|K|m|M)?(?:\s?[-–]\s?[$€£]?\s?\d[\d\s,\.]*\s?(?:k|K|m|M)?)?)",
        posting_body,
    )
    if salary_match:
        salary = salary_match.group(1).strip()

    posted_at = ""
    posted_match = re.search(
        r"(?:posted|publication|publi\u00e9|date)\s*[:\-]\s*([^\n]{2,80})",
        posting_body,
        flags=re.IGNORECASE,
    )
    if posted_match:
        posted_at = posted_match.group(1).strip()

    body_chars = str(len(posting_body))

    return {
        "Applied at": applied_ts,
        "Source URL": job_url,
        "Source domain": source_domain,
        "Company": company_name,
        "Position": position_title,
        "Posting title": posting_title,
        "Role track": str(role),
        "Output language": output_language,
        "Location": location,
        "Work mode": work_mode,
        "Employment type": employment_type,
        "Salary": salary,
        "Posted at": posted_at,
        "Snapshot body chars": body_chars,
    }


def _cleanup_snapshot_latex_artifacts(output_dir: Path, tex_stem: str) -> None:
    # Keep only Markdown + PDF snapshot; remove compilation leftovers.
    for suffix in (".aux", ".log", ".out", ".tex"):
        path = output_dir / f"{tex_stem}{suffix}"
        if path.exists():
            try:
                path.unlink()
            except Exception as exc:
                logger.warning(f"Could not remove snapshot artifact {path.name}: {exc}")


def _run_latex(
    engine: str,
    tex_file: str,
    work_dir: Path,
    runs: int = 1,
) -> None:
    """
    Run the LaTeX engine `runs` times in work_dir.
    Raises RuntimeError on non-zero exit code.
    """
    cmd = [
        engine,
        "-interaction=nonstopmode",
        "-halt-on-error",
        tex_file,
    ]
    for i in range(runs):
        logger.debug(f"[{engine}] run {i+1}/{runs}: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=work_dir,
            capture_output=True,
            text=False,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")

        if result.returncode != 0:
            # Emit last 40 lines of log for diagnosis
            tail = "\n".join(stdout.splitlines()[-40:])
            logger.error(f"Captured output:\n{tail}")
            if stderr:
                logger.error(f"Captured stderr:\n{stderr}")
            raise RuntimeError(
                f"{engine} exited with code {result.returncode} for {tex_file}"
            )


def _find_template_file(directory: Path, role: RoleType, template_name: str) -> str:
    """
    Search for the best-matching .tex file in the directory based on role and template name.
    """
    # 1. Exact match e.g. CV_AI_Data_Lato.tex
    role_map = {"ai": "AI_Data", "it": "IT_Infra", "phd": "PhD"}
    role_str = role_map.get(role, "AI_Data")
    
    candidates = [
        f"CV_{role_str}_{template_name.capitalize()}.tex",
        f"CV_{role_str}.tex",
        f"CV_{role.upper()}.tex",
    ]
    
    for c in candidates:
        if (directory / c).exists():
            return c
            
    # 2. Fuzzy match: first .tex containing role keyword
    for f in directory.glob("*.tex"):
        if role_str.lower() in f.name.lower() or role.lower() in f.name.lower():
            return f.name
            
    # 3. Any .tex
    first_tex = next(directory.glob("*.tex"), None)
    if first_tex:
        return first_tex.name
        
    return "CV_AI_Data.tex"  # Default fallback name
