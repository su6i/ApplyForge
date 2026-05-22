"""
altacv_renderer.py — Generate a tailored CV .tex string from profile + LLM selections using AltaCV.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from src.core.tex_utils import latex_escape

if TYPE_CHECKING:
    from src.pipeline.content_tailor import TailoredContent


_DOC_PREAMBLE = r"""\documentclass[7pt,a4paper,withhyper]{altacv}

\geometry{left=0.9cm,right=0.9cm,top=0.7cm,bottom=0.7cm,columnsep=0.3cm}
\usepackage{paracol}

\usepackageFONT_USEPACKAGE_PLACEHOLDER
\usepackage{ragged2e}
\linespread{GLOBAL_LINE_SPREAD_PLACEHOLDER}

\definecolor{VividPurple}{HTML}{3E0097}
\definecolor{SlateGrey}{HTML}{2E2E2E}
\definecolor{LightGrey}{HTML}{666666}

\colorlet{name}{black}
\colorlet{tagline}{VividPurple}
\colorlet{heading}{VividPurple}
\colorlet{headingrule}{VividPurple}
\colorlet{subheading}{VividPurple}
\colorlet{accent}{VividPurple}
\colorlet{emphasis}{SlateGrey}
\colorlet{body}{LightGrey}

\renewcommand{\itemmarker}{{\small\textbullet}}
\renewcommand{\ratingmarker}{\faCircle}
\renewcommand{\taglinefont}{\Large\bfseries}

\renewcommand{\cvevent}[4]{%
  {\large\color{emphasis}\raggedright #1\par}
  \smallskip\normalsize
  \ifstrequal{#2}{}{}{%
    \textbf{\color{accent}#2}%
  }%
  \ifstrequal{#4}{}{}{%
    \ifstrequal{#2}{}{}{\hspace{1.5em}}%
    {\small\cvLocationMarker~#4}%
  }%
  \ifstrequal{#3}{}{}{%
    \hfill{\small\cvDateMarker~#3}%
  }\par
}

\begin{document}
\enlargethispage{GLOBAL_PAGE_ENLARGE_PLACEHOLDER}
"""

_DOC_END = r"""
\end{paracol}
\end{document}
"""

# ==============================================================================
# LAYOUT & SPACING CONFIGURATION
# ==============================================================================

# ──────────────────────────────────────────────────────────────────────────────
# GLOBAL SETTINGS
# ──────────────────────────────────────────────────────────────────────────────
GLOBAL_LINE_SPREAD = "0.95"  # Slightly tighter line spacing for one-page fit
GLOBAL_PAGE_ENLARGE = "5cm"  # Vertical expansion to prevent overflow to second page

# ──────────────────────────────────────────────────────────────────────────────
# FONT FAMILY CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────
# Change FONT_FAMILY to one of these options:
#   "lato"            - Modern sans-serif (default)
#   "helvet"          - Helvetica sans-serif
#   "phv"             - PostScript Helvetica
#   "times"           - Times New Roman serif (DEFAULT FOR NOW - USE THIS!)
#   "palatino"        - Palatino serif
#   "bookman"         - Bookman serif
#   "courier"         - Courier monospace
FONT_FAMILY = "lato"

# Font package configuration mapping (don't change these unless you know what you're doing)
_FONT_CONFIG = {
    "lato":     {"package": "lato",      "option": "default"},
    "helvet":   {"package": "helvet",    "option": "scaled"},
    "phv":      {"package": "phv",       "option": ""},
    "times":    {"package": "times",     "option": ""},
    "palatino": {"package": "palatino",  "option": ""},
    "bookman":  {"package": "bookman",   "option": ""},
    "courier":  {"package": "courier",   "option": ""},
}

# ──────────────────────────────────────────────────────────────────────────────
# HEADING AND BODY TEXT STYLES
# ──────────────────────────────────────────────────────────────────────────────
HEADING_FONT_COMMAND = r"{\bfseries\large}"  # Font style for section headings (bold/large)
BODY_FONT_COMMAND = r"{\normalsize}"         # Font style for body text (normal size)

# ──────────────────────────────────────────────────────────────────────────────
# CONTACT SECTION (Email, Phone, Location, LinkedIn, GitHub)
# ──────────────────────────────────────────────────────────────────────────────
CONTACT_TOP_MARGIN = "\\vspace{-0.5em}"           # Space before section starts
CONTACT_ITEM_VERTICAL_SPACING = "\\vspace{0.1em}" # Vertical gap between each contact line

# ──────────────────────────────────────────────────────────────────────────────
# PROFILE SECTION (Summary paragraph at top)
# ──────────────────────────────────────────────────────────────────────────────
PROFILE_TOP_MARGIN = "\\vspace{0em}"  # Space reserved before profile section

# ──────────────────────────────────────────────────────────────────────────────
# SKILLS SECTION (Tags and categorized skills)
# ──────────────────────────────────────────────────────────────────────────────
SKILLS_TOP_MARGIN = "\\vspace{0.1em}"             # Space before skills section
SKILLS_CATEGORY_VERTICAL_SPACING = "\\vspace{0.2em}" # Gap between skill categories

# ──────────────────────────────────────────────────────────────────────────────
# EXPERIENCE SECTION (Job positions and employment history)
# ──────────────────────────────────────────────────────────────────────────────
EXPERIENCE_TOP_MARGIN = "\\vspace{-0.5em}"          # Space before experience section
EXPERIENCE_ENTRY_DIVIDER = "\\divider"              # Visual separator between jobs
EXPERIENCE_HIGHLIGHTS_GAP = "\\smallskip"           # Gap between job header and bullet points

# ──────────────────────────────────────────────────────────────────────────────
# PROJECTS SECTION (Personal and professional projects)
# ──────────────────────────────────────────────────────────────────────────────
PROJECTS_TOP_MARGIN = "\\vspace{-1.5ex}"     # Space before projects section
PROJECTS_ENTRY_DIVIDER = "\\divider"         # Visual separator between projects

# ──────────────────────────────────────────────────────────────────────────────
# CERTIFICATIONS SECTION (Courses, certificates, credentials)
# ──────────────────────────────────────────────────────────────────────────────
CERTIFICATIONS_TOP_MARGIN = "\\vspace{-1.5ex}"        # Space before certifications section
CERTIFICATIONS_BEFORE_CONTENT = "\\vspace{0.4em}"     # Internal alignment correction
CERTIFICATIONS_TOP_BOTTOM_PADDING = "\\vspace{0.2em}" # Top/bottom padding when not filling
CERTIFICATIONS_ITEM_VERTICAL_SPACING = "\\vspace{0.25em}" # Gap between certificates
CERTIFICATIONS_LEFT_INDENT = "\\hspace*{0.5em}"       # Left indentation for issuer headings
CERTIFICATIONS_DISTRIBUTE_TO_FILL = True              # Stretch spacing to fill available height
CERTIFICATIONS_ISSUER_INDENT = "1em"                  # Indentation level under issuer heading

# ──────────────────────────────────────────────────────────────────────────────
# LANGUAGES SECTION (Proficiency levels in languages)
# ──────────────────────────────────────────────────────────────────────────────
LANGUAGES_TOP_MARGIN = "\\vspace{0em}"                # Space before languages section
LANGUAGES_ITEM_VERTICAL_SPACING = "\\vspace{0.15em}" # Gap between each language entry

# ──────────────────────────────────────────────────────────────────────────────
# HOBBIES SECTION (Interests and activities)
# ──────────────────────────────────────────────────────────────────────────────
HOBBIES_TOP_MARGIN = "\\vspace{0em}"  # Space before hobbies section
HOBBIES_BOTTOM_PADDING = "\\vspace{0.1em}"  # Bottom padding to extend blue background

# ──────────────────────────────────────────────────────────────────────────────
# EDUCATION SECTION (Degrees, institutions, certifications)
# ──────────────────────────────────────────────────────────────────────────────
EDUCATION_TOP_MARGIN = "\\vspace{0em}"        # Space before education section
EDUCATION_ENTRY_DIVIDER = "\\divider"         # Visual separator between education entries

# ──────────────────────────────────────────────────────────────────────────────
# RIGHT COLUMN SEPARATOR CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────
# Toggle separators and choose visual style between "dotted" and "dashed".
# Use "default" to keep the section's original divider command.
ENABLE_RIGHT_COLUMN_SEPARATORS = True
RIGHT_COLUMN_SEPARATOR_STYLE = "dashed"  # Options: dotted | dashed | default | none
RIGHT_COLUMN_DOTTED_SEPARATOR = (
    "\\vspace{0.25em}\\noindent{\\color{black!25}\\dotfill}\\par\\vspace{0.25em}"
)
RIGHT_COLUMN_DASHED_SEPARATOR = (
    "\\vspace{0.25em}\\noindent{\\color{black!30}"
    "\\leavevmode\\cleaders\\hbox to 0.9em{\\hss--\\hss}\\hfill\\kern0pt}"
    "\\par\\vspace{0.25em}"
)

# ──────────────────────────────────────────────────────────────────────────────
# CONTENT LIMITS (Maximum items to display per section)
# ──────────────────────────────────────────────────────────────────────────────
MAX_EXPERIENCE_HIGHLIGHTS = 4  # Max bullet points per job
MAX_PROJECTS = 3               # Max projects to show

_TEXT = {
    "en": {
        "contact": "Contact",
        "profile": "Profile",
        "skills": "Skills",
        "experience": "Experience",
        "projects": "Projects",
        "education": "Education",
        "languages": "Languages",
        "hobbies": "Hobbies",
        "certifications": "Certifications",
        "tech": "Tech",
    },
    "fr": {
        "contact": "Coordonnees",
        "profile": "Profil",
        "skills": "Competences",
        "experience": "Experience",
        "projects": "Projets",
        "education": "Formation",
        "languages": "Langues",
        "hobbies": "Centres d'interet",
        "certifications": "Certifications",
        "tech": "Technos",
    },
}


def render(profile: dict, tailored: "TailoredContent") -> str:
    language = tailored.language if tailored.language in ("fr", "en") else "en"

    # Determine font LaTeX syntax from mapping
    font_config = _FONT_CONFIG.get(FONT_FAMILY, _FONT_CONFIG["times"])
    font_pkg = font_config["package"]
    font_opt = font_config["option"]
    
    # Build LaTeX font line: either [option]{package} or {package}
    if font_opt:
        font_line = f"[{font_opt}]{{{font_pkg}}}"
    else:
        font_line = f"{{{font_pkg}}}"
    
    # Inject global settings into preamble
    preamble = _DOC_PREAMBLE.replace("GLOBAL_LINE_SPREAD_PLACEHOLDER", GLOBAL_LINE_SPREAD)
    preamble = preamble.replace("GLOBAL_PAGE_ENLARGE_PLACEHOLDER", GLOBAL_PAGE_ENLARGE)
    preamble = preamble.replace("FONT_USEPACKAGE_PLACEHOLDER", font_line)
    sections: list[str] = [preamble]

    # Name and Identity
    identity = profile.get("identity", {})
    # --- HEADER / IDENTITY ---
    name = identity.get("name", "")
    
    cv_title = tailored.position_title or identity.get("title", "AI & IT Infrastructure Engineer")
        
    sections.append(f"\\name{{{latex_escape(name)}}}")
    sections.append(f"\\tagline{{{latex_escape(cv_title)}}}")

    # Personal info
    email = identity.get("email", "")
    phone = identity.get("phone", "")
    location = identity.get("location", "")
    linkedin = identity.get("linkedin", "")
    github = identity.get("github", "")

    sections.append("\\personalinfo{}")
    sections.append("\\makecvheader")

    # Profile summary (Full Width)
    summary = tailored.cv_summary or profile.get("profile_summary", "")
        
    if summary:
        sections.append(_section_profile(summary, language))

    # Start paracol columns with new ratio (narrow left, wide right)
    sections.append("\\columnratio{0.35}")
    
    if hasattr(tailored, "color_theme") and tailored.color_theme:
        color_map = {
            "blue": "E6F0FA",
            "green": "E8F4E9",
            "orange": "FFF3E0",
            "red": "FFEBEE",
            "purple": "F3E5F5",
            "gray": "F5F5F5"
        }
        theme = tailored.color_theme.lower().strip()
        hex_color = color_map.get(theme)
        if not hex_color:
            hex_color = theme.lstrip("#")
        
        # Super basic manual validation: roughly check if it looks like a hex string
        if len(hex_color) in (3, 6) and all(c in "0123456789ABCDEFabcdef" for c in hex_color):
            # Ultra tight top gap to save space
            sections.append("\\vspace{0.1em}")
            sections.append(f"\\backgroundcolor{{c[0]}}[HTML]{{{hex_color.upper()}}}")
            sections.append("\\vspace{0.1em}")

    sections.append("\\begin{paracol}{2}")
    
    # --- ROW 1: [Contact, Skills] | [Experience] ---
    sections.append(CONTACT_TOP_MARGIN)
    sections.append(_section_contact(email, phone, location, linkedin, github, language))
    
    sections.append(SKILLS_TOP_MARGIN)
    sections.append(
        _section_skills(
            profile.get("skills", {}), tailored.tailored_skills, tailored.variant, language
        )
    )
    
    sections.append("\\switchcolumn")
    sections.append(EXPERIENCE_TOP_MARGIN)
    experience = tailored.selected_experience or profile.get("experience", [])
    if experience:
        sections.append(_section_experience(experience, language))
    
    # Ensure no extra space at the bottom of Row 1 right
    sections.append("\\vfill")
    
    # Sync Row 2: Certifications and Projects
    sections.append("\\switchcolumn*")
    
    certs = profile.get("certifications", [])
    if certs:
        sections.append(CERTIFICATIONS_TOP_MARGIN)
        sections.append(_section_certifications(certs, language))
    
    sections.append("\\switchcolumn")
    sections.append(PROJECTS_TOP_MARGIN)
    projects = tailored.selected_projects or profile.get("projects", [])
    if projects:
        sections.append(_section_projects(projects[:MAX_PROJECTS], language))
    
    # Balanced sync point for Row 2
    sections.append("\\vfill")
    
    # Synchronize and switch back to left column (Top-align Row 3)
    sections.append("\\switchcolumn*")

    # --- ROW 3: [Languages, Hobbies] | [Education] ---
    sections.append(LANGUAGES_TOP_MARGIN)
    languages = profile.get("languages", {})
    if languages:
        sections.append(_section_languages(languages, language))
    hobbies = profile.get("hobbies", [])
    if hobbies:
        sections.append(_section_hobbies(hobbies, language))
    
    # Ensure left column background stretches to match right column height
    sections.append("\\vfill")
    
    sections.append("\\switchcolumn")
    sections.append(EDUCATION_TOP_MARGIN)
    education = profile.get("education", [])
    if education:
        sections.append(_section_education(education, language))

    sections.append(_DOC_END)
    return "\n".join(sections)

def _section_contact(
    email: str,
    phone: str,
    location: str,
    linkedin: str,
    github: str,
    language: str,
) -> str:
    sections = [f"\\cvsection{{{_label('contact', language)}}}\n\\smallskip"]
    items = []
    if email:
        items.append(f"\\textcolor{{accent}}{{\\faAt}} \\hspace{{0.5em}} \\href{{mailto:{email}}}{{{latex_escape(email)}}}")
    if phone:
        items.append(f"\\textcolor{{accent}}{{\\faPhone}} \\hspace{{0.5em}} {latex_escape(phone)}")
    if location:
        items.append(f"\\textcolor{{accent}}{{\\cvLocationMarker}} \\hspace{{0.5em}} {latex_escape(location)}")
    if linkedin:
        li_url = f"https://{linkedin}" if not linkedin.startswith("http") else linkedin
        items.append(f"\\textcolor{{accent}}{{\\faLinkedin}} \\hspace{{0.5em}} \\href{{{li_url}}}{{{latex_escape(linkedin)}}}")
    if github:
        gh_url = f"https://{github}" if not github.startswith("http") else github
        items.append(f"\\textcolor{{accent}}{{\\faGithub}} \\hspace{{0.5em}} \\href{{{gh_url}}}{{{latex_escape(github)}}}")
    
    # Join items with a LaTeX line break, then configured vertical spacing.
    if items:
        separator = f"\\\\{CONTACT_ITEM_VERTICAL_SPACING}\n"
        joined_items = separator.join(items)
        sections.append(joined_items + r" \par")
    
    return "\n".join(sections) + "\n\n"

def _section_profile(summary: str, language: str) -> str:
    return (
        f"\\cvsection{{{_label('profile', language)}}}\n"
        f"{{\\small\\justifying {latex_escape(summary)}\\par}}\n"
    )


def _label(key: str, language: str) -> str:
    lang = language if language in _TEXT else "en"
    return _TEXT[lang].get(key, key)


def _right_col_divider(default_divider: str) -> str:
    """Return configured right-column separator or section default divider."""
    if not ENABLE_RIGHT_COLUMN_SEPARATORS:
        return default_divider

    style = RIGHT_COLUMN_SEPARATOR_STYLE.strip().lower()
    if style == "dotted":
        return RIGHT_COLUMN_DOTTED_SEPARATOR
    if style == "dashed":
        return RIGHT_COLUMN_DASHED_SEPARATOR
    if style in ("none", "off"):
        return ""
    return default_divider

def _section_experience(experience: list[dict], language: str) -> str:
    items: list[str] = [f"\\cvsection{{{_label('experience', language)}}}\n"]
    for job in experience:
        company = latex_escape(job.get("company", ""))
        location = latex_escape(job.get("location", ""))
        role = latex_escape(job.get("role", ""))
        period = latex_escape(job.get("period", ""))
        highlights = job.get("highlights", [])[:MAX_EXPERIENCE_HIGHLIGHTS]
        tech = job.get("tech", [])

        items.append(f"\\cvevent{{{role}}}{{{company}}}{{{period}}}{{{location}}}")
        items.append(EXPERIENCE_HIGHLIGHTS_GAP)
        if highlights:
            items.append("\\begin{itemize}[leftmargin=1.25em, itemsep=0pt, parsep=0pt]")
            for h in highlights:
                items.append(f"\\item \\justifying {latex_escape(h)}")
            items.append("\\end{itemize}")
            
        if tech:
            items.append(
                "\\smallskip\\noindent\\textit{"
                + _label("tech", language)
                + ": }"
                + latex_escape(", ".join(tech[:6]))
                + "\\par"
            )
        else:
            items.append("\\par")
            
        sep = _right_col_divider(EXPERIENCE_ENTRY_DIVIDER)
        if sep:
            items.append(sep)

    res = "\n".join(items).strip()
    sep = _right_col_divider(EXPERIENCE_ENTRY_DIVIDER)
    if res.endswith(sep):
        res = res[:-len(sep)]
    return res + "\n\n"

def _section_projects(projects: list[dict], language: str) -> str:
    items: list[str] = [f"\\cvsection{{{_label('projects', language)}}}\n"]
    for proj in projects[:MAX_PROJECTS]:
        title = latex_escape(proj.get("title", ""))
        period = latex_escape(proj.get("period", ""))
        desc = latex_escape(proj.get("description", ""))
        highlights = proj.get("highlights", [])
        tech = proj.get("tech", [])
        url = proj.get("url", "")

        # Format: bold title with period on same line, no type shown
        title_with_period = f"\\textbf{{{title}}} {{\\footnotesize\\color{{LightGrey}}{period}}}"
        if url:
            title_with_period = f"\\href{{{url}}}{{{title_with_period}}}"
        
        # Use empty strings for type (2nd param) and location (4th param) to hide them
        items.append(f"\\cvevent{{{title_with_period}}}{{}}{{}}{{}}") 
        
        if desc:
            items.append(f"{{\\justifying {desc}\\smallskip\\par}}")
        if highlights:
            items.append("\\begin{itemize}[leftmargin=1.25em, nosep]")
            for h in highlights[:4]: # Limit to 4 highlights for space
                items.append(f"\\item \\justifying {latex_escape(h)}")
            items.append("\\end{itemize}")
            
        if tech:
            items.append(
                "\\smallskip\\noindent\\textit{"
                + _label("tech", language)
                + ": }"
                + latex_escape(", ".join(tech[:8]))
                + "\\par"
            )
        else:
            if not desc:
                items.append("\\par")
        
        sep = _right_col_divider(PROJECTS_ENTRY_DIVIDER)
        if sep:
            items.append(sep)

    res = "\n".join(items).strip()
    sep = _right_col_divider(PROJECTS_ENTRY_DIVIDER)
    if res.endswith(sep):
        res = res[:-len(sep)]
    return res + "\n\n"

def _section_skills(
    skills_dict: dict,
    tailored_skills: list[str],
    role: str = "ai",
    language: str = "en",
) -> str:
    items = [f"\\cvsection{{{_label('skills', language)}}}"]

    already_shown: set[str] = set()

    if language == "fr":
        labels = {
            "ai_ml": "IA \\& ML",
            "mlops_devops": "MLOps \\& DevOps",
            "networks_support": "Reseaux \\& Support",
            "data": "Donnees",
        }
    else:
        labels = {
            "ai_ml": "AI \\& ML",
            "mlops_devops": "MLOps \\& DevOps",
            "networks_support": "Networks \\& Support",
            "data": "Data",
        }

    if role == "it":
        categories = [
            ("networks_support", labels["networks_support"]),
            ("mlops_devops", labels["mlops_devops"]),
            ("ai_ml", labels["ai_ml"]),
            ("data", labels["data"]),
        ]
    else:
        categories = [
            ("ai_ml", labels["ai_ml"]),
            ("mlops_devops", labels["mlops_devops"]),
            ("networks_support", labels["networks_support"]),
            ("data", labels["data"]),
        ]

    for key, label in categories:
        cat_skills = skills_dict.get(key, [])
        filtered = [s for s in cat_skills if s not in already_shown]
        if filtered:
            items.append(f"\\cvachievement{{\\faCode}}{{{label}}}{{{latex_escape(', '.join(filtered[:6]))}}}\\par")
            items.append(SKILLS_CATEGORY_VERTICAL_SPACING)

    return "\n".join(items) + "\n\n"

def _section_education(education: list[dict], language: str) -> str:
    items: list[str] = [f"\\cvsection{{{_label('education', language)}}}"]
    for edu_item in education:
        degree = latex_escape(edu_item.get("degree", ""))
        institution = latex_escape(edu_item.get("institution", ""))
        period = latex_escape(edu_item.get("period", ""))
        honors_raw = str(edu_item.get("honors", "") or "")
        honors_lines = [latex_escape(line.strip()) for line in honors_raw.splitlines() if line.strip()]
        honors = r"\\ ".join(honors_lines)

        # Make degree bold and prominent
        bold_degree = f"\\textbf{{{degree}}}"
        items.append(f"\\cvevent{{{bold_degree}}}{{{institution}}}{{{period}}}{{}}")
        if honors:
            items.append(f"\\textit{{{honors}}}\\par")
        else:
            items.append("\\par")
        
        sep = _right_col_divider(EDUCATION_ENTRY_DIVIDER)
        if sep:
            items.append(sep)

    res = "\n".join(items).strip()
    sep = _right_col_divider(EDUCATION_ENTRY_DIVIDER)
    if res.endswith(sep):
        res = res[:-len(sep)]
    return res + "\n\n"

def _section_languages(languages: dict, language: str) -> str:
    items = [f"\\cvsection{{{_label('languages', language)}}}"]
    if languages:
        fr_lang_map = {
            "French": "Francais",
            "English": "Anglais",
            "Persian": "Persan",
        }
        lang_parts = []
        for lang, level in languages.items():
            display_lang = fr_lang_map.get(lang, lang) if language == "fr" else lang
            lang_parts.append(f"\\textbf{{{latex_escape(display_lang)}}} ({latex_escape(level)})")
        # Join languages with LaTeX line breaks and spacing for vertical display
        items.append(f"\\\\{LANGUAGES_ITEM_VERTICAL_SPACING}\n".join(lang_parts) + r"\par")
    return "\n".join(items) + "\n\n"

def _section_hobbies(hobbies: list[str], language: str) -> str:
    items = [f"\\cvsection{{{_label('hobbies', language)}}}"]
    if hobbies:
        # Keep a compact 2-per-line layout to avoid section overflow/splitting.
        for idx in range(0, len(hobbies), 2):
            row = hobbies[idx: idx + 2]
            row_tags = " ".join(f"\\cvtag{{{latex_escape(hobby)}}}" for hobby in row)
            items.append(row_tags + r"\\[-0.15em]")
        # Force background extension with invisible phantom content that takes vertical space
        items.append(r"\phantom{X}\\[0.1em]")
    return "\n".join(items) + "\n\n"

def _section_certifications(certs: list[str], language: str) -> str:
    items = [f"\\cvsection{{{_label('certifications', language)}}}"]
    if certs:
        items.append(CERTIFICATIONS_BEFORE_CONTENT)
        if CERTIFICATIONS_DISTRIBUTE_TO_FILL:
            # Stretch top/between/bottom gaps to fill available vertical room.
            items.append("\\vspace*{\\fill}")
        else:
            items.append(CERTIFICATIONS_TOP_BOTTOM_PADDING)

        grouped: dict[str, list[str]] = {}
        for cert in certs:
            issuer, cert_title = _split_cert_issuer(cert)
            grouped.setdefault(issuer, []).append(cert_title)

        issuer_rows = list(grouped.items())
        for idx, (issuer, cert_list) in enumerate(issuer_rows):
            items.append(
                "\\noindent"
                f"{CERTIFICATIONS_LEFT_INDENT}"
                f"\\textbf{{{latex_escape(issuer)}}}\\par"
            )
            for cert_title in cert_list:
                items.append(
                    "\\noindent"
                    f"{CERTIFICATIONS_LEFT_INDENT}\\hspace{{{CERTIFICATIONS_ISSUER_INDENT}}}"
                    f"\\raisebox{{0.15ex}}{{\\textcolor{{accent}}{{\\scriptsize\\faStar}}}} "
                    f"{latex_escape(cert_title)}\\par"
                )
            if CERTIFICATIONS_DISTRIBUTE_TO_FILL:
                if idx < len(issuer_rows) - 1:
                    items.append("\\vspace*{\\fill}")
            else:
                items.append(CERTIFICATIONS_ITEM_VERTICAL_SPACING)

        if not CERTIFICATIONS_DISTRIBUTE_TO_FILL and items and items[-1] == CERTIFICATIONS_ITEM_VERTICAL_SPACING:
            items.pop()

        if CERTIFICATIONS_DISTRIBUTE_TO_FILL:
            items.append("\\vspace*{\\fill}")
        else:
            items.append(CERTIFICATIONS_TOP_BOTTOM_PADDING)
    return "\n".join(items) + "\n\n"


def _split_cert_issuer(cert: str) -> tuple[str, str]:
    """Return (issuer, certificate title) for grouped certifications rendering."""
    text = (cert or "").strip()
    if not text:
        return "Autres", ""

    if ":" in text:
        left, right = text.split(":", 1)
        if len(left.strip()) <= 30:
            return left.strip(), right.strip()

    if " — " in text:
        left, right = text.rsplit(" — ", 1)
        issuer = right.strip()
        issuer = issuer.split("(", 1)[0].strip() or "Autres"
        return issuer, left.strip()

    return "Autres", text
