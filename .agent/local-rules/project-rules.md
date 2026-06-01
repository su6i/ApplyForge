# CV Workspace — All Rules

> This file is authoritative. Any AI agent working in this repo MUST read it before making changes.

---

## R1 — Single Source of Truth

| Data | File |
|---|---|
| Personal info (name, email, phone, addresses) | `templates/shared/personal_data.tex` |
| Same data for Python/automation | `templates/shared/personal_data.json` |
| Shared LaTeX packages + macros | `templates/lato/lato_macros.tex` |

**Never hardcode name, email, phone or location directly in any `.tex` file.**  
Always use the macros: `\cvname`, `\cvemail`, `\cvphone`, `\cvlocation`, `\cvlinkedin`, `\cvgithub`.

---

## R2 — No Persian / Non-Latin Characters in FR/EN CVs

Any `.tex` file destined for the French or English market **MUST NOT** contain Persian (Farsi) or non-Latin Unicode characters **except** in the `Languages` section where the language name itself may appear.

Common dangerous substitutions that slip in:
- و → et / and
- برای → pour / for
- با → avec / with
- در → dans / in

**Verify before every commit:**
```bash
./verify.py
# or manual grep:
perl -ne 'print "$ARGV:$.: $_" if /[^\x00-\x7f]/' templates/lato/*.tex
```

---

## R3 — Compile from `templates/lato/`

LaTeX resolves `\input{lato_macros}` relative to the **source file's directory**.  
Always compile from inside `templates/lato/`, not from `/tmp` or root.

**Correct:**
```bash
./compile.sh          # builds all, puts PDFs in output/
./compile.sh ai       # only CV_AI_Data_Lato
```

**Or manually:**
```bash
cd templates/lato
pdflatex -output-directory=/tmp -interaction=nonstopmode CV_AI_Data_Lato.tex
cp /tmp/CV_AI_Data_Lato.pdf ../../output/
```

---

## R4 — Output Always Goes to `output/` at Repo Root

- **Source of truth for final PDFs**: `<repo-root>/output/`
- `templates/lato/output/` is a legacy/internal copy — do not use for distribution
- After every compile, copy PDFs to root `output/`
- Root `output/` is git-tracked (PDFs committed)

---

## R5 — Only `.tex`, `.pdf`, `.json`, `.md` Are Git-Tracked

The `.gitignore` blocks all other file types.  
Never force-add `.aux`, `.log`, `.fls`, `.synctex.gz`, `.jpg`, `.png`, `.docx`, `.gz`.

---

## R6 — Applied/ Naming Convention

New job application folders MUST follow:
```
Applied/YYYY-MM_CompanyName_Role/
```
Example: `Applied/2026-02_Natixis_DataScientist/`

Inside each folder:
```
Applied/2026-02_Natixis_DataScientist/
├── CV_Natixis.pdf          ← compiled from one of the Lato templates
├── CV_Natixis.tex          ← optional: customized copy of the template
└── LM_Natixis.pdf          ← cover letter (if sent)
```

---

## R7 — Adding a New CV Template

1. Create a new `.tex` file in `templates/lato/`:
   ```latex
   \documentclass[11pt,a4paper]{article}
   \input{lato_macros}
   \input{../shared/personal_data}
   % Optional overrides:
   \renewcommand{\itemspace}{\vspace{0.15em}}
   \begin{document}
   \cvheader{Job Title Here}
   % ... sections using \cvsection, \headerrow, \itemspace ...
   \end{document}
   ```
2. Compile — no script changes needed (auto-discovered):
   ```bash
   ./compile.sh CV_NewRole_Lato   # just this one
   ./compile.sh all               # rebuilds everything
   ```

---

## R8 — Spacing Rules

| Variable | Default | When to override |
|---|---|---|
| `\itemspace` | `0.2em` | Shrink to `0.15em` if page is slightly over |
| `\sectionspace` | `\vfill` | Never change — distributes space evenly |
| First section gap | `0.25em` | Controlled by `\iffirstsection` in `lato_macros.tex` |
| geometry | top/bot `0.3in`, lr `0.4in` | Widen slightly if too cramped |

**If page overflows:** Reduce `\itemspace` first, then try `9pt` bullet font, then tighten geometry.  
**If too much white at bottom:** `\vfill` should handle it automatically — check for hardcoded `\vspace`.

---

## R9 — latexmk Cache Bug

If pdflatex throws a persistent cached error:
```bash
cd templates/lato && latexmk -C CV_IT_Infra_Lato.tex
```

---

## R10 — Hyperlinks

All CVs use `hyperref` (loaded in `lato_macros.tex` with `[hidelinks]`).  
In the printed PDF links are invisible but clickable (ATS-friendly).  
Email uses `mailto:` scheme, LinkedIn/GitHub use `https://` scheme.  
The `\cvheader{}` macro wraps all three automatically.

---

## R11 — Cover Letters

- Reusable templates live in `cover_letters/*.tex`
- Compiled PDFs go to `cover_letters/output/*.pdf`
- The templates use **4 mandatory `\newcommand` variables** at the top:
  `\CompanyName`, `\PositionTitle`, `\Variant`, `\WhyThisCompany`
- Per-application copies (filled + compiled) go inside `Applied/<folder>/`
- The automation pipeline (`latex_builder.py`) fills these automatically

---

## R12 — Git Commit Convention

```
type: short summary (max 72 chars)

[optional body]
```

Types: `cv:`, `init:`, `fix:`, `refactor:`, `docs:`, `scripts:`

Example: `cv: update Su6i-Yar project with MiniMax 2.5 + fal.ai details`

---

## R13 — personal_data.json for Job Applier

`personal_data.json` is the Python job-applier's source of truth.  
**Always sync it with `personal_data.tex` after any contact info change.**  
Fields: `name`, `location`, `mobility`, `email`, `phone`, `linkedin`, `github`, `languages`, `certifications`.

---

## R14 — Never Commit Directly to `main`

A pre-commit hook blocks direct commits to `main`.  
**Always create a feature branch first:**
```bash
git checkout -b feature/describe-your-change
# ... make changes and compile ...
git add ...
git commit -m "cv: description"
git checkout main
git merge feature/describe-your-change
```

---

## R15 — Python Pipeline Rules

| Module | Input | Output |
|---|---|---|
| `job_scraper.py` | Job URL | `JobPosting.body` (cleaned text) |
| `role_classifier.py` | body text | `"ai"` / `"it"` / `"phd"` |
| `content_tailor.py` | body + role | `TailoredContent` dataclass |
| `latex_builder.py` | role + content | Two PDFs in `Applied/` |
| `service.py` | URL | `ApplicationBundle` |

**Never change cover letter template body text.** The variants (AI vs IT paragraphs)  
are in the LaTeX `\ifthenelse` blocks — the Python pipeline only fills the 4 variables.

**LaTeX engine mapping:**
- CV templates → `pdflatex` (uses `lato` font, not `fontspec`)
- Cover letter templates → `xelatex` (uses `fontspec` + Times New Roman)

**Environment variables** (all in `.env`, never committed):
- `OPENAI_API_KEY` — required for all LLM calls
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — required for bot mode only
- `AUTO_APPLY` — set `true` to skip approval buttons
- `LLM_MODEL` — default `gpt-4o-mini`

---

## R16 — Applied/ Folder Naming (Auto-generated)

The pipeline creates `Applied/YYYY-MM_CompanySlug_RoleSlug/` automatically.  
Slug rules: alphanumeric, CamelCase, no spaces, max 4 words per slug.  
Example: `Applied/2026-02_Capgemini_DataScientistSenior/`

Inside each generated folder:
```
Applied/2026-02_Capgemini_DataScientistSenior/
├── CV_AI_Data_Lato.tex        ← copy of template
├── CV_AI_Data_Lato.pdf        ← compiled with pdflatex
├── CoverLetter_Capgemini.tex  ← instantiated template
├── CoverLetter_Capgemini.pdf  ← compiled with xelatex
└── shared/                    ← personal_data.tex (for \input{../shared/personal_data})
```
---

## R17 — README vs docs/ Separation *(Cross-project standard)*

This rule applies to **every project**, not just this CV repo.

### The rule

| File/folder | Audience | Content |
|---|---|---|
| `README.md` | **End users** — people who will *use* the project | What it does, how to install, how to use, where files land. No internal architecture, no code references, no git internals. |
| `docs/` | **Developers & AI agents** — people who will *build or maintain* the project | Architecture, module reference, data flow, technical decisions, LaTeX internals, git workflow. |

### README must contain (and nothing else)
1. One-sentence description of what the project does
2. First-time setup (numbered steps)
3. How to perform the core action (e.g. generate an application, run the bot)
4. Where to find the output files
5. How to update the main user-facing data (e.g. contact info, CV content)
6. A table linking to `docs/` files for technical details

### README must NOT contain
- Architecture diagrams or pipeline descriptions
- LaTeX macro tables
- Git workflow or branch conventions
- Environment variable reference (beyond "open `.env` and fill in your keys")
- Source code file references (e.g. `src/pipeline/job_scraper.py`)
- Troubleshooting for developers (compilation flags, latexmk cache, etc.)

### docs/ structure (minimum for any project)

```
docs/
├── architecture.md    ← system design, data flow, module reference
└── ...                ← any additional technical guides as needed
```

Add more files as the project grows. Name them by topic, not by audience.

### Enforcement

When an AI agent edits `README.md`, it must ask: *"Would a non-technical user
need to know this?"* If no → move it to `docs/`.

When an AI agent creates a new project, it must create `docs/architecture.md`
before writing any code, and must keep `README.md` under 150 lines.

---

## R18 — Single Core, Multiple Interfaces *(Cross-project standard)*

> **"Build once in the core. Expose everywhere."**
> No feature logic may live in an interface layer — ever.

### The rule

Every project with more than one interface (CLI, API, Bot, Web …)
**MUST** designate a single canonical core service class.
All interfaces are thin wrappers around that core.

In this project the core is `ApplicationService` (`src/pipeline/service.py`).

### Interface hierarchy

```
ApplicationService              ← ONLY place where pipeline logic lives
        │
        ├── CLI   (main.py)           → service.generate()
        ├── Bot   (src/bot/)          → service.generate()
        ├── API   (src/api/, future)  → service.generate()
        └── Web   (src/web/, future)  → service.generate()
```

### Rules for new features

1. **Implement in core first.** Add the feature as a method or parameter on
   `ApplicationService` (or a `src/pipeline/` module it delegates to).
2. **Then expose through interfaces.** Add CLI flag / bot command / API endpoint
   that calls the core. No logic duplication.
3. **Never add pipeline logic to an interface.** If a bot needs extra behaviour,
   add it to the core; the bot just calls it.
4. **Shared dataclasses only.** `ApplicationBundle`, `TailoredContent`,
   `JobPosting` are shared across all interfaces. Never create parallel
   response types per interface.

### Quality checks are automatic

All quality guards (`src/core/quality_guard.py`) run automatically inside
`latex_builder.py` before every compilation. No interface should call
`verify.py` or any quality function manually.

### Anti-patterns to avoid

| ❌ Wrong | ✅ Correct |
|---|---|
| Bot command has its own scraping logic | Bot calls `service.generate()` |
| API re-implements role classification | Core classifies; API receives result |
| CLI and Bot duplicate `match_score` display | `ApplicationBundle` carries data; each interface formats it |
| Running `python3 verify.py` manually | Quality guard runs inside `build()` automatically |

### Enforcement

When adding a new feature, an AI agent MUST:
1. Check whether `ApplicationService` already exposes a method for it.
2. If not, add it to the core first (with docstring), then wire the interface.
3. Challenge any code that adds > 5 lines of "pipeline-looking" logic inside
   `main.py`, a bot handler, or a route handler — it belongs in the core.

---

## R19 — Docs Must Stay in Sync with Code *(Cross-project standard)*

> **"If you changed the code, you changed the docs."**
> Documentation rot is a bug. Treat it as one.

### The rule

Every time an AI agent adds, removes, or renames:
- a pipeline step or module
- a public method on `ApplicationService`
- a CLI command or flag
- a dataclass field
- a configuration variable
- an architectural decision

…it **MUST** update the relevant `docs/` file in the **same commit**.

### Which doc to update

| Changed | Update |
|---|---|
| `src/pipeline/*` or `src/core/*` | `docs/architecture.md` |
| `main.py` commands | `docs/architecture.md` + `README.md` (usage section) |
| `src/bot/*` | `docs/bot-setup.md` |
| Git workflow / branching | `docs/git-workflow.md` |
| LaTeX templates | `docs/latex-templates.md` |
| Any of the above | Mirror changes to `docs/fa/` (Persian) |

### Enforcement

- Doc-only commits are **not** acceptable after a code change. Docs travel
  with the code that necessitated them, in the same commit.
- When reviewing AI-generated changes, if a code file changed but its
  corresponding doc did not, the change is **incomplete** — send it back.
- The `README.md` usage section must reflect the actual current CLI commands
  at all times. If `main.py` gains a new command, `README.md` must show it.

### What counts as "docs"

- `docs/*.md` and `docs/fa/*.md` — primary technical docs
- `README.md` — user-facing usage summary
- `.agents/rules.md` — architectural decisions and constraints
- Inline docstrings on public functions/classes (these are also docs)