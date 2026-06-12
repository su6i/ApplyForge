# Architecture — Automation Pipeline

[Back to README](../README.md) | [LaTeX Templates](latex-templates.md) | [Bot Setup](bot-setup.md) | [Git Workflow](git-workflow.md)

## Overview

The pipeline takes a job posting URL and produces two compiled PDFs:
a tailored CV and a tailored cover letter. The whole process runs in ~30 seconds.

```
Job URL
  │
  ▼  src/pipeline/job_scraper.py
Fetch & clean page text
(requests → BeautifulSoup; Selenium headless fallback for JS-rendered pages)
  │
  ▼  src/pipeline/role_classifier.py
LLM classifies into one of three tracks:
  "ai"   → AI Engineer / Data Scientist / ML / Python Developer
  "it"   → IT Support / Network / Infrastructure
  "phd"  → PhD / Research / Academic
  │
  ▼  src/pipeline/content_tailor.py
LLM extracts four cover-letter variables:
  company_name       → exact name from the posting
  position_title     → exact job title
  language           → "fr" or "en" (detected from posting language)
  variant            → "ai"/"it" (FR) or "ai"/"python" (EN)
  why_this_company   → 2-3 company-specific sentences in the posting's language
  │
  ▼  src/pipeline/latex_builder.py
• Select CV template (role → file mapping below)
• Availability guard: abort if posting body contains expiry signals
  ("plus disponible", "offre clôturée", etc.) — prevents wasted generation
• Select cover letter template (language → FR or EN template)
• Copy files into Applied/YYYY-MM-DD_CompanySlug_Role_lang/ workspace
• Fill cover letter: regex-replace the 4 \newcommand placeholders
  Note: personal_data.tex provides \cvlinkedin and \cvgithub as full paths
  (e.g. "linkedin.com/in/su6i") — templates must NOT prepend the base URL.
• Generate standardized filenames: {CV_OWNER_SLUG}-{DocumentType}_{Role}_{Language}.tex
• pdflatex ×2  →  CV.pdf
• xelatex  ×1  →  CoverLetter.pdf
  │
  ▼
Applied/2026-05-19_Capgemini_AI_fr/
    {CV_OWNER_SLUG}-CV_AI_fr.pdf
    {CV_OWNER_SLUG}-LettreMotivation_AI_fr.pdf
    (shared/ folder with personal_data.tex)
```

---

## Module Reference

| File | Class/Function | Input → Output |
|---|---|---|
| `job_scraper.py` | `scrape(url)` | URL → `JobPosting` (`.body` text) |
| `role_classifier.py` | `classify(body)` | text → `"ai"` / `"it"` / `"phd"` |
| `content_tailor.py` | `tailor(body, role, resume_profile="")` | text + role + optional resume profile → `TailoredContent` (includes `match_score`, `tailored_skills`, `cv_summary`, `cv_tagline`, `selected_experience`, `selected_projects`, `extra_education`) |
| `latex_builder.py` | `build(role, content, profile: dict | None = None)` | role + content + optional profile → `ApplicationBundle` (CV can be generated dynamically from `profile`) |
| `service.py` | `ApplicationService.generate(url)` | URL → `ApplicationBundle` |

### Dataclasses

```python
@dataclass
class JobPosting:
    url: str
    title: str
    body: str          # cleaned plain text used by all downstream modules

@dataclass
class TailoredContent:
  company_name: str
  position_title: str        # exact job title from posting (used for metadata/folder naming)
  language: Literal["fr", "en"]
  variant: str               # value written into \Variant in the .tex file
  why_this_company: str
  match_score: int = 0
  tailored_skills: list[str] = field(default_factory=list)
  cv_summary: str = ""                    # 3-5 line tailored profile paragraph
  cv_tagline: str = ""                    # short professional title for CV header (3-5 words, not the job title)
  color_theme: str = ""                   # sidebar background color (from profile json, e.g. "blue")
  selected_experience: list[dict] = field(default_factory=list)  # reduced set chosen for this job
  selected_projects: list[dict] = field(default_factory=list)
  extra_education: list[dict] = field(default_factory=list)  # conditional education (enforced in service.py)

@dataclass
class ApplicationBundle:
    output_dir: Path
    cv_pdf: Path
    cl_pdf: Path
```

---

## Role → Template Mapping

| Role | CV template | CL template | LaTeX engine |
|---|---|---|---|
| `ai` | `CV_AI_Data_Lato.tex` | `Cover_Letter_Template_En.tex` (EN) or `Cover_Letter_Template_Fr.tex` (FR) | pdflatex / xelatex |
| `it` | `CV_IT_Infra_Lato.tex` | `Cover_Letter_Template_Fr.tex` | pdflatex / xelatex |
| `phd` | `CV_PhD_Lato.tex` | `Cover_Letter_Template_En.tex` | pdflatex / xelatex |

**LaTeX engine split:**
- CV templates use `pdflatex` — they load the `lato` font via `fontenc`, not `fontspec`
- Cover letter templates use `xelatex` — they load `fontspec` + Times New Roman

---

## Scraper Strategy

`job_scraper.py` tries two methods in order:

1. **requests + BeautifulSoup** — fast, no browser required. Noise tags
   (`script`, `style`, `nav`, `header`, `footer`, `aside`) are stripped,
   then plain text is extracted and whitespace-normalized.
2. **Selenium headless Chrome** — fallback when the extracted text is shorter
   than 300 characters (sign of a JS-rendered page). Uses the same
   `chrome_browser_options()` helper as the bot browser.

---

## LLM Usage

| Step | Model | Temperature | Max tokens | Purpose |
|---|---|---|---|---|
| `classify()` | `gpt-4o-mini` | 0 | 10 | One-word classification — deterministic |
| `tailor()` | `gpt-4o-mini` | 0.4 | — | JSON extraction — slight creativity for `why_this_company` |

Both use `langchain-openai` via `ChatOpenAI`.
Input texts are truncated to 6 000 / 8 000 chars to stay within context limits.

---

## Output Folder Structure

```
Applied/2026-05-19_Capgemini_AI_fr/
├── lato_macros.tex                              ← copied from templates/lato/
├── {CV_OWNER_SLUG}-CV_AI_fr.tex                 ← rendered by pipeline
├── {CV_OWNER_SLUG}-CV_AI_fr.pdf                 ← compiled with pdflatex
├── {CV_OWNER_SLUG}-LettreMotivation_AI_fr.tex   ← instantiated from cover_letters/
├── {CV_OWNER_SLUG}-LettreMotivation_AI_fr.pdf   ← compiled with xelatex
└── shared/
    └── personal_data.tex                        ← copied from templates/shared/
```

The `shared/` sibling dir is required so that `\input{../shared/personal_data}`
resolves correctly when compiling the CV from inside the application folder.

---

## Output Naming Convention

As of the latest update, all generated CV and cover letter files follow a standardized naming pattern:

**Pattern:** `Firstname_LASTNAME-{DocumentType}_{Role}_{Language}.{ext}`

**Components:**
- **DocumentType**: `CV` or `LettreMotivation` (FR) / `CoverLetter` (EN)
- **Role**: `AI`, `IT`, `PhD`, or other role identifier
- **Language**: `fr` or `en`
- **Extension**: `.tex` or `.pdf`

**Examples:**
- `Firstname_LASTNAME-CV_IT_fr.pdf` — IT infrastructure CV in French
- `Firstname_LASTNAME-LettreMotivation_AI_fr.pdf` — AI role cover letter in French
- `Firstname_LASTNAME-CV_PhD_en.pdf` — PhD application CV in English

**Rationale:**
- Immediate human recognition: candidate name + document type visible in filesystem
- Consistent across all generated applications
- Company name preserved in folder structure (`Applied/2026-02_CompanyName_Role/`)
- Simplifies archival and application tracking

**Implementation:** Standardization applied in `src/pipeline/latex_builder.py` lines 216–220
via the `_build_cover_letter()` function.
