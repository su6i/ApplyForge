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
pip install -r requirements.txt
```

**Step 2 — Create your personal profile**

```bash
cp master_cv.example.json master_cv.json
```

Edit `master_cv.json` with your real name, contact info, work history, and skills.
This file is private and gitignored — it never gets committed.

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

pip install -r requirements.txt
```
```bash
# 2) Copy env and set your OpenAI key

cp .env.example .env
# Edit .env and set OPENAI_API_KEY (and TELEGRAM_* if using the bot)
```

```bash
# 3) Create the internal profile (accepts .tex, .pdf, .jpg/.png)
Examples:

uv run main.py init-profile --cv templates/lato/CV_AI_Data_Lato.tex
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
  - `pdfminer.six`, `pytesseract`, and `Pillow` are Python dependencies (in `requirements.txt`).
  - `tesseract` OCR engine must be installed on your system for OCR to work.
    On macOS: `brew install tesseract`.
- If you only use a LaTeX `.tex` source, you do NOT need `tesseract` or the OCR
  Python packages — the `.tex` path works without extra system deps.
- The `--template` flag for `apply` supports `altacv` (default) and `lato`.

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

**`templates/altacv/`** — AltaCV style (xelatex), used for spontaneous applications:

| File | Use for |
|---|---|
| `CV_AI_MLOps_fr.tex` | AI / MLOps roles (French) |
| `CV_AI_MLOps_en.tex` | AI / MLOps roles (English) |
| `CV_DevOps_Alternance_fr.tex` | DevOps alternance (French) |
| `CV_Polyvalent_fr.tex` | Polyvalent / interim agency (French) |

**`templates/lato/`** — Lato/article style (pdflatex):

| File | Use for |
|---|---|
| `CV_AI_Data_Lato.tex` | AI / Data Science / Python roles (English) |
| `CV_IT_Infra_Lato.tex` | IT Support / Network roles (French) |
| `CV_PhD_Research_en.tex` | PhD / Research applications (English) |

**`templates/classic/`** — ModernCV banking style (pdflatex), 16 role variants.

After editing a lato or classic template, rebuild the PDF:

```bash
./compile.sh ai    # CV_AI_Data_Lato
./compile.sh it    # CV_IT_Infra_Lato
./compile.sh phd   # CV_PhD_Research_en
./compile.sh all   # rebuild all CV_*.tex across all template folders
```

---

## Spontaneous Applications

Generate a pre-written CV without LLM — no job URL needed:

```bash
uv run main.py spontaneous ai                    # AI / MLOps (French)
uv run main.py spontaneous ai-en                 # AI / MLOps (English)
uv run main.py spontaneous mlops                 # MLOps (French)
uv run main.py spontaneous mlops-en              # MLOps (English)
uv run main.py spontaneous devops                # DevOps (French)
uv run main.py spontaneous devops-alternance     # DevOps alternance (French)
uv run main.py spontaneous phd                   # PhD / Research (English)
uv run main.py spontaneous polyvalent            # Polyvalent / interim (French)

# Add --city to select Montpellier vs Grenoble automatically:
uv run main.py spontaneous ai --city montpellier
```

Output goes to `Applied/YYYY-MM-DD_Spontannee_{role}_{lang}/`.

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

Contact details are in `templates/shared/personal_data.tex` (private, not committed).
