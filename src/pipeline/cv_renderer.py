"""
cv_renderer.py — Generate a tailored CV .tex string from profile + LLM selections.

This module is responsible for dynamically building a complete LaTeX CV document
from two inputs:
  1. The full candidate profile dict (data/resume_profile.json) — the "life database".
  2. The TailoredContent returned by the LLM — which items to include for THIS job.

The LLM selects the most relevant experience highlights, projects, and skills
for the specific job. This renderer then formats those selections into a valid
.tex file that follows the lato_macros template conventions.

This replaces the previous approach of copying the `.tex` template verbatim
(which produced the same CV for every application).

Fallback behaviour:
  If a tailored field is empty (e.g. selected_experience = []), the renderer
  falls back to the full profile data so compilation never fails.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.tex_utils import latex_escape, itemize

if TYPE_CHECKING:
    from src.pipeline.content_tailor import TailoredContent


_DOC_PREAMBLE = r"""\documentclass[10pt,a4paper]{article}
\input{lato_macros}
\input{../shared/personal_data}
\renewcommand{\itemspace}{\vspace{0.25em}}

\begin{document}
"""

_DOC_END = r"\end{document}"


def render(profile: dict, tailored: "TailoredContent") -> str:
    """
    Produce a complete LaTeX CV document string, tailored to the job.

    Parameters
    ----------
    profile  : Full candidate profile loaded from resume_profile.json.
    tailored : LLM output with cv_summary, selected_experience, selected_projects,
               tailored_skills, and position_title.

    Returns
    -------
    A string that can be written directly to a .tex file and compiled with pdflatex.
    """
    sections: list[str] = [_DOC_PREAMBLE]

    # Header — use position_title as subtitle if available
    cv_title = tailored.position_title or profile.get("identity", {}).get("title", "")
    sections.append(f"\\cvheader{{{latex_escape(cv_title)}}}\n")

    # Profile summary
    summary = tailored.cv_summary or profile.get("profile_summary", "")
    if summary:
        sections.append(_section_profile(summary))

    # Technical skills (ordered by tailored_skills from LLM)
    sections.append(_section_skills(profile.get("skills", {}), tailored.tailored_skills))

    # Professional experience (LLM-selected subset)
    experience = tailored.selected_experience or profile.get("experience", [])
    if experience:
        sections.append(_section_experience(experience))

    # Key projects (LLM-selected subset)
    projects = tailored.selected_projects or profile.get("projects", [])
    if projects:
        sections.append(_section_projects(projects))

    # Education (always full — never filtered)
    education = profile.get("education", [])
    if education:
        sections.append(_section_education(education))

    # Languages & Certifications (always full)
    languages = profile.get("languages", {})
    certifications = profile.get("certifications", [])
    if languages or certifications:
        sections.append(_section_languages_certs(languages, certifications))

    sections.append(_DOC_END)
    return "\n".join(sections)


# ─── Section renderers ────────────────────────────────────────────────────────

def _section_profile(summary: str) -> str:
    return (
        "\\cvsection{Profile}\n"
        "\\noindent\n"
        f"{latex_escape(summary)}\n"
    )


def _section_skills(skills_dict: dict, tailored_skills: list[str]) -> str:
    """
    Render the skills table.

    If the LLM provided tailored_skills, those are shown as a single
    prioritised row at the top. All other skill categories follow.
    """
    rows: list[str] = []

    if tailored_skills:
        top = ", ".join(r"\textbf{" + latex_escape(s) + "}" if i == 0 else latex_escape(s)
                        for i, s in enumerate(tailored_skills[:12]))
        rows.append(f"\\textbf{{Key Skills}} & {top} \\\\")

    category_labels = {
        "ai_ml":        "AI \\& ML",
        "data":         "Data",
        "mlops_infra":  "MLOps \\& Infra",
        "visualization": "Viz \\& Tools",
        "languages_prog": "Languages",
    }
    for key, label in category_labels.items():
        items = skills_dict.get(key, [])
        if not items:
            continue
        # Remove duplicates already shown in tailored_skills row
        already_shown = set(tailored_skills[:12]) if tailored_skills else set()
        filtered = [s for s in items if s not in already_shown]
        if not filtered:
            continue
        row_content = ", ".join(latex_escape(s) for s in filtered)
        rows.append(f"\\textbf{{{label}}} & {row_content} \\\\")

    if not rows:
        return ""

    row_text = "\n".join(rows)
    return (
        "\\cvsection{Technical Skills}\n"
        "\\noindent\n"
        "\\begin{tabularx}{\\linewidth}{@{} p{3.2cm} X @{}}\n"
        f"{row_text}\n"
        "\\end{tabularx}\n"
    )


def _section_experience(experience: list[dict]) -> str:
    items: list[str] = []
    for job in experience:
        company   = latex_escape(job.get("company", ""))
        location  = latex_escape(job.get("location", ""))
        role      = latex_escape(job.get("role", ""))
        period    = latex_escape(job.get("period", ""))
        highlights = job.get("highlights", [])
        tech       = job.get("tech", [])

        header = (
            f"    \\item\n"
            f"    \\headerrow{{\\textbf{{{company}"
            f"{', ' + location if location else ''}"
            f"}}, \\emph{{{role}}}}}{{{period}}}\n"
            "    \\begin{itemize}[leftmargin=1.5em, label={\\textbullet}, nosep]\n"
        )
        bullets = "\n".join(
            f"        \\item {latex_escape(h)}" for h in highlights[:4]  # max 4 bullets
        )
        if tech:
            tech_line = (
                "\n        \\item \\emph{"
                + latex_escape(", ".join(tech[:6]))
                + "}"
            )
        else:
            tech_line = ""

        items.append(header + bullets + tech_line + "\n    \\end{itemize}\n    \\itemspace")

    body = "\n".join(items).rstrip("\\itemspace").rstrip()
    return (
        "\\cvsection{Professional Experience}\n"
        "\\begin{itemize}[leftmargin=1em, label={}]\n"
        f"{body}\n"
        "\\end{itemize}\n"
    )


def _section_projects(projects: list[dict]) -> str:
    items: list[str] = []
    for proj in projects[:3]:  # max 3 projects for 1-page CV
        title  = latex_escape(proj.get("title", ""))
        period = latex_escape(proj.get("period", ""))
        desc   = latex_escape(proj.get("description", ""))
        tech   = proj.get("tech", [])

        tech_line = (
            "\\emph{" + latex_escape(", ".join(tech[:8])) + "}"
            if tech else ""
        )

        item = (
            "    \\item\n"
            f"    \\headerrow{{\\textbf{{{title}}} | \\emph{{Personal Project}}}}{{{period}}}\n"
            "    \\begin{itemize}[leftmargin=1.5em, label=$\\bullet$, nosep]\n"
            f"        \\item {desc}\n"
        )
        if tech_line:
            item += f"        \\item {tech_line}\n"
        item += "    \\end{itemize}\n    \\itemspace"
        items.append(item)

    body = "\n".join(items).rstrip("\\itemspace").rstrip()
    return (
        "\\cvsection{Key Projects}\n"
        "\\begin{itemize}[leftmargin=1em, label={}]\n"
        f"{body}\n"
        "\\end{itemize}\n"
    )


def _section_education(education: list[dict]) -> str:
    items: list[str] = []
    for edu in education:
        degree      = latex_escape(edu.get("degree", ""))
        institution = latex_escape(edu.get("institution", ""))
        period      = latex_escape(edu.get("period", ""))
        honors      = edu.get("honors", "")

        item = (
            "    \\item\n"
            f"    \\headerrow{{\\textbf{{{degree}}}}}{{{period}}}\n"
            "    \\begin{itemize}[leftmargin=1.5em, label=$\\bullet$, nosep]\n"
            f"        \\item {institution}\n"
        )
        if honors:
            item += f"        \\item {latex_escape(honors)}\n"
        item += "    \\end{itemize}\n    \\itemspace"
        items.append(item)

    body = "\n".join(items).rstrip("\\itemspace").rstrip()
    return (
        "\\cvsection{Education}\n"
        "\\begin{itemize}[leftmargin=1em, label={}]\n"
        f"{body}\n"
        "\\end{itemize}\n"
    )


def _section_languages_certs(languages: dict, certifications: list[str]) -> str:
    rows: list[str] = []

    if languages:
        lang_str = ", ".join(
            f"\\textbf{{{latex_escape(lang)}}} ({latex_escape(level)})"
            for lang, level in languages.items()
        )
        rows.append(f"\\textbf{{Languages}} & {lang_str} \\\\")

    if certifications:
        cert_str = ", ".join(
            f"\\textbf{{{latex_escape(c)}}}" for c in certifications
        )
        rows.append(f"\\textbf{{Certifications}} & {cert_str} \\\\")

    if not rows:
        return ""

    row_text = "\n".join(rows)
    return (
        "\\cvsection{Languages \\& Certifications}\n"
        "\\noindent\n"
        "\\begin{tabularx}{\\linewidth}{@{} p{3.2cm} X @{}}\n"
        f"{row_text}\n"
        "\\end{tabularx}\n"
    )
