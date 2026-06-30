# Git Workflow

[Back to README](../README.md) | [Architecture](architecture.md) | [LaTeX Templates](latex-templates.md) | [Bot Setup](bot-setup.md)

## Branch Policy

A pre-commit hook **blocks direct commits to `main`**.
Always work on a feature branch.

```bash
git checkout -b feature/describe-your-change
# … make changes, compile, test …
git add ...
git commit -m "type: short summary"
git checkout main
git merge feature/describe-your-change
```

---

## Commit Types

| Prefix | When to use |
|---|---|
| `cv:` | Content change in a CV (bullet text, title, section) |
| `feat:` | New feature (new template, new pipeline module) |
| `fix:` | Bug fix or compilation fix |
| `refactor:` | Code restructure with no behaviour change |
| `docs:` | Documentation only |
| `applied:` | Archiving a job application |
| `scripts:` | Changes to `compile.sh` or other shell scripts |

### Examples
```
cv: update Su6i-Yar project with MiniMax 2.5 details
feat: add banking template style
fix: xelatex Times New Roman fallback to TeX Gyre Termes
applied: Capgemini — Ingénieur Data — 2026-02-26
docs: add bot-setup guide
```

---

## Tracked & Ignored File Types

The `.gitignore` uses a **whitelist strategy**: everything is ignored by default,
safe file types are explicitly un-ignored.

**Tracked (committed):**

| Type | Reason |
|---|---|
| `.tex` | LaTeX CV and cover letter templates |
| `.md` | Documentation, LinkedIn carousel source |
| `.sh` `.zsh` | Build and install scripts |
| `.py` `.mjs` | Python and Node.js scripts |
| `.env.example` | Config template — placeholders only, no real secrets |
| `.gitignore` | This file |
| `examples/master_cv.example.json` | Anonymised profile structure — safe to commit |

**Always ignored (never commit):**

| Path / Pattern | Reason |
|---|---|
| `.env` | API keys and tokens |
| `.linkedin_token.json` | OAuth token — regenerate with `--auth` if lost |
| `master_cv.json` | Your real personal profile data |
| `master_cv*.json` (except example) | Any variant of the personal profile |
| `Applied/` | Job applications — names, letters, rejections |
| `linkedin/idees_posts.md` | Personal post backlog and strategy |
| `data/` | Scraped cache and profile data |
| `output/` | Generated PDFs |
| `*.pdf` `.txt` | Generated output files |
| LaTeX artifacts | `.aux` `.fls` `.fdb_latexmk` `.synctex.gz` `.log` `.out` |
| `__pycache__/` `*.pyc` `*.pyo` | Python bytecode |
| `.venv/` | Virtual environment |
| `log/` `*.tmp` | Runtime and temp files |
| `scratch*.py` | Throwaway scratch scripts |
| `.jpg` `.png` `.docx` `.xlsx` `.gz` `.zip` | Binary/media files |
| `.DS_Store` | macOS metadata |

---

## New Job Application Workflow

```bash
# 1. Run the pipeline (creates Applied/ folder automatically)
uv run main.py apply https://company.com/jobs/123 [--template altacv]

# 2. Review the PDFs
open "Applied/2026-02_Company_Role/CV_AI_Data_Lato.pdf"
open "Applied/2026-02_Company_Role/CoverLetter_Company.pdf"

# 3. Commit
git checkout -b applied/2026-02-company-role
git add "Applied/2026-02_Company_Role/"
git commit -m "applied: CompanyName — Role — 2026-02-26"
git checkout main && git merge applied/2026-02-company-role
```

---

## Manual CV Update Workflow

```bash
# 1. Edit
nano templates/lato/CV_AI_Data_Lato.tex

# 2. Compile & check
./compile.sh ai
open output/CV_AI_Data_Lato.pdf

# 3. Commit
git checkout -b feature/update-ai-cv
git add templates/lato/CV_AI_Data_Lato.tex output/CV_AI_Data_Lato.pdf
git commit -m "cv: update …"
git checkout main && git merge feature/update-ai-cv
```
