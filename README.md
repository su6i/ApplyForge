<div align="center">
  <img src="assets/project_logo.jpg" width="350" alt="ApplyForge Logo">
  <h1>ApplyForge - Automated CV &amp; Cover Letter Crafter</h1>

  <br>

  <p align="center" style="white-space: nowrap;">
    <img src="https://img.shields.io/badge/Version-0.1.0-blue.svg" alt="Version">&nbsp;<img src="https://img.shields.io/badge/Python-3.12+-yellow.svg" alt="Python">&nbsp;<img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">&nbsp;<a href="https://www.linkedin.com/in/su6i/"><img src="assets/linkedin_su6i.svg" height="20" alt="LinkedIn"></a>
  </p>
</div>

**What it does:** You send a job posting link — the system reads it, picks the right CV,
writes a personalised cover letter, and delivers two ready-to-send PDFs.

---

## First-Time Setup

**Step 1 — Install dependencies** *(run once)*

```bash
uv sync
```

**Step 2 — Create your personal profile**

```bash
cp examples/master_cv.example.json master_cv.json
```

Edit `master_cv.json` with your real name, contact info, work history, and skills.
This file is private and gitignored — it never gets committed.
`CLAUDE.md` (AI agent instructions) is also gitignored as it may contain personal workflow details.

**Step 3 — Add your API keys**

```bash
cp .env.example .env
```

Open `.env` and fill in:
- `CV_OWNER_SLUG` — your name slug used in all output filenames (e.g. `Firstname_LASTNAME`)
- `LLM_MODEL` — LLM model identifier (e.g. `deepseek-v4-flash` for DeepSeek, or `gpt-4o` for OpenAI)
- `OPENAI_API_KEY` or `DEEPSEEK_API_KEY` — depending on your chosen LLM provider
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` — only needed for the Telegram bot
  *(see [docs/bot-setup.md](docs/bot-setup.md))*

**Step 4 — Verify everything is working**

```bash
uv run main.py test
```

---

## Generating an Application

## Quickstart (minimal)

If you want to try the tool quickly, run these commands from the repository root:

```bash
# 1) Install Python deps

uv sync
```
```bash
# 2) Copy env and set your OpenAI key

cp .env.example .env
# Edit .env and set OPENAI_API_KEY (and TELEGRAM_* if using the bot)
```

```bash
# 3) Create the internal profile (accepts .tex, .pdf, .jpg/.png)
Examples:

uv run main.py init-profile --cv templates/lato/CV_AI_en.tex
uv run main.py init-profile --cv path/to/my_cv.pdf
uv run main.py init-profile --cv path/to/photo_of_cv.jpg
```
```bash
# 4) Generate an application from a job URL (optional: pass --cv to override)

uv run main.py apply https://company.com/jobs/12345
uv run main.py apply https://company.com/jobs/12345 --cv path/to/my_cv.pdf
```
```bash
# 5) Or start the Telegram bot and use /apply from your phone

uv run main.py bot
```

```bash
# 6) Quick health check

uv run main.py test
```

Notes:
- The `--cv` flag for `init-profile` and `apply` accepts `.tex`, `.pdf`, and common
  image formats (`.jpg`, `.jpeg`, `.png`, `.webp`).
- PDF extraction and image OCR require additional system/software:
  - `pdfminer.six`, `pytesseract`, and `Pillow` are Python dependencies (declared in `pyproject.toml`).
  - `tesseract` OCR engine must be installed on your system for OCR to work.
    On macOS: `brew install tesseract`.
- If you only use a LaTeX `.tex` source, you do NOT need `tesseract` or the OCR
  Python packages — the `.tex` path works without extra system deps.
- The `--template` flag for `apply` supports `altacv` (default) and `lato`.
- The `--licence` flag for `apply` forces inclusion of the conditional electronics degree.
- The pipeline automatically blocks applications that require: Permis B, fonctionnaire status, French nationality, or Secret Défense clearance.
- For **Technicien-tier** postings (catégorie B, Bac+2/3 keywords), the pipeline automatically drops the DU degree, filters Master honors to Réseaux/Systèmes modules only, and normalizes experience titles from "Ingénieur" to "Technicien" — no LLM involved.
- **Bilingual master CV**: `data/master_cv_en.json` (English source of truth) and `data/master_cv_fr.json` (French). When `--lang fr` is used, the pipeline loads `CV_<Role>_fr_source.json` and generates it from `master_cv_fr.json` if absent — experience titles, degrees, and certifications are French from the start, no manual translation needed.

### Option A — Telegram (easiest)

Start the bot:
```bash
uv run main.py bot
```

Then in Telegram, send:
```
/apply https://company.com/jobs/your-job-link
```

The bot will:
1. Read the job posting
2. Generate a tailored CV + cover letter (takes ~30 seconds)
3. Send you both PDFs to review
4. Ask **Approve** or **Reject**
   - **Approve** → saves both files to your private archive channel
   - **Reject** → nothing is saved

### Option B — Terminal

```bash
uv run main.py apply https://company.com/jobs/your-job-link
```

The two PDFs are saved in the `Applied/` folder.

---

## Where Are My Files?

| What | Where |
|---|---|
| Generated applications (CV + cover letter per job) | `Applied/YYYY-MM-DD_Company_Role/` |
| Spontaneous applications (no company) | `Applied/YYYY-MM-DD_Spontannee_Role_lang/` |

**Output Filenames:** All generated CVs and cover letters follow the standardized naming pattern:
```
{CV_OWNER_SLUG}-{DocumentType}_{Role}_{Language}.{ext}
```

The slug is set via `CV_OWNER_SLUG` in your `.env` file. Examples:
- `Firstname_LASTNAME-CV_IT_fr.pdf` — IT infrastructure CV (French)
- `Firstname_LASTNAME-LettreMotivation_AI_fr.pdf` — AI cover letter (French)
- `Firstname_LASTNAME-CV_PhD_en.pdf` — PhD application CV (English)

This naming convention makes it easy to identify document type and role at a glance.

---

## Updating Your CVs

### Change your contact info (name, email, phone, location)

Edit **one file only**:

```
templates/shared/personal_data.tex
```

All CVs pull from this file — you never need to update the same detail in multiple places.

### Change CV content (work experience, skills, etc.)

Templates are organized by style family:

Filenames follow `CV_<Label>_<lang>.tex`, matching the role labels in
`config/roles.yaml` and the profile JSON files (`…-CV_<Label>_source.json`).

**`templates/altacv/`** — AltaCV style (xelatex), used for spontaneous applications:

| File | Role | Use for |
|---|---|---|
| `CV_AI_fr.tex` / `CV_AI_en.tex` | `ai` | AI / MLOps roles |
| `CV_DevOpsAlternance_fr.tex` | `devops`, `devops_alternance` | DevOps (alternance layout) |
| `CV_Polyvalent_fr.tex` | `polyvalent` | Polyvalent / interim agency (French) |
| `CV_Python_fr.tex` | `python` | Generalist Python (placeholder copy of Polyvalent) |

**`templates/lato/`** — Lato/article style (pdflatex):

| File | Role | Use for |
|---|---|---|
| `CV_AI_en.tex` | `ai` | AI / Data Science / Python roles (English) |
| `CV_Support_fr.tex` | `support` | IT Support / Network technicien (French) |
| `CV_PhD_en.tex` | `phd` | PhD / Research applications (English) |

**`templates/classic/`** — ModernCV banking style (pdflatex), 16 role variants.

After editing a lato or classic template, rebuild the PDF:

```bash
./compile.sh ai        # CV_AI_en
./compile.sh support   # CV_Support_fr
./compile.sh phd       # CV_PhD_en
./compile.sh all       # rebuild all CV_*.tex across all template folders
```

---

## Spontaneous Applications

Generate a pre-written CV without LLM — no job URL needed:

```bash
uv run main.py spontaneous python                # Generalist Python (French)
uv run main.py spontaneous ai                    # AI / MLOps (French)
uv run main.py spontaneous ai-en                 # AI / MLOps (English)
uv run main.py spontaneous devops                # DevOps (French)
uv run main.py spontaneous devops_alternance     # DevOps alternance / work-study (French)
uv run main.py spontaneous support               # Network / support technicien (French)
uv run main.py spontaneous phd                   # PhD / Research (English)
uv run main.py spontaneous polyvalent            # Polyvalent / interim (French)

# Add --city to select Montpellier vs Grenoble automatically:
uv run main.py spontaneous ai --city montpellier
```

Output goes to `Applied/YYYY-MM-DD_Spontannee_{role}_{lang}/`.

---

## Roles Registry (`config/roles.yaml`)

All CV tracks are defined in one file: **`config/roles.yaml`**. The role
classifier, filename labels, CV + spontaneous template maps, cover-letter
variant, and per-role skill ordering are all derived from it — nothing is
hardcoded elsewhere.

Canonical roles: **`general`**, **`devops`**, **`ai`**, **`phd`**. Each entry
lists `aliases` that route fuzzy or legacy inputs to a canonical role (e.g.
`it`, `network` → `devops`; `python`, `mlops` → `ai`; `polyvalent` → `general`).
Append `-en`/`-fr` to a spontaneous role to override its language (`ai-en`).

**Add a new role** by adding an entry under `roles:` — or auto-scaffold one
(clones a base template stub + registers the entry):

```python
from src.core import roles
roles.scaffold_role("cloud", base="devops", lang="fr")
```

Run the registry contract tests with:

```bash
python tests/test_roles.py        # or: pytest tests/test_roles.py
```

---

## Updating Your Cover Letter

Open the relevant template in `cover_letters/`:

| File | Language |
|---|---|
| `Cover_Letter_Template_Fr.tex` | French |
| `Cover_Letter_Template_En.tex` | English |

Only edit the **stock paragraphs** (the text that describes your experience).
The personalisation variables at the top (`\CompanyName`, `\PositionTitle`, etc.)
are filled automatically for each application — do not touch them.

**Cover letter body is now fully LLM-generated.** `\CLIntro` and `\CLBody` are
written by the LLM based on the actual job posting — no hardcoded variant blocks.
The LLM adapts tone and content: technical for IT/AI roles, transferable-skills focused
for maintenance or industrial roles.

---

## Data Scraping (France Travail)

### Scrape job-market stats for data roles

```bash
node scripts/data_jobs_scraper.mjs
```

Reads ROME codes from `docs/it_rome_codes.json`, visits
`candidat.francetravail.fr/metierscope/fiche-metier/{CODE}/` for each role,
extracts national offer count and candidate count, saves to `docs/data_jobs_stats.json`.

Key ROME codes for data jobs:

| Code | Métier |
|---|---|
| M1405 | Data Scientist |
| M1419 | Data Analyst |
| M1811 | Data Engineer |
| M1889 | Ingénieur IA |
| M1872 | Consultant BI |

**Note:** France Travail uses non-breaking spaces as thousands separators (`"3 830"`).
The scraper strips all non-digit characters before parsing numbers.

---

## Technical Documentation

For developers, AI agents, or anyone who wants to understand the internals:

| Topic | File |
|---|---|
| How the pipeline works (scraping, LLM, compilation) | [docs/architecture.md](docs/architecture.md) |
| LaTeX macros, template structure, adding new styles | [docs/latex-templates.md](docs/latex-templates.md) |
| Telegram bot setup, AUTO_APPLY, source files | [docs/bot-setup.md](docs/bot-setup.md) |
| Git workflow, commit conventions, tracked files | [docs/git-workflow.md](docs/git-workflow.md) |

---

## Contact

Contact details live in the personal-data vault outside the repo
(`~/.local/share/agent-projects/applyforge/shared/personal_data.tex`, override with
`APPLYFORGE_DATA_DIR`) — private, never committed.
