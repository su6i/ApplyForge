# Agent Operating Guide — CV Repository

> READ THIS FIRST before any action in this workspace.
> Also read: `.agents/rules.md` (all project rules) and `.agents/skills/knowledge.md` (technical details).

---

## Identity of This Workspace

This is a **personal CV repository**. It contains:
- LaTeX CV templates (in `templates/lato/`) — the active, production-quality ones
- Personal information macros (`personal_data.tex`, `personal_data.json`)
- Applied job applications (`Applied/`)
- Cover letter templates (`cover_letters/`)

**Primary language:** French (CVs) and English (CVs + this codebase)  
**Never output Persian characters in `.tex` files** (→ Rule R2 in `.agents/rules.md`)

---

## Mandatory Pre-Flight Checks

Before making ANY edit to a `.tex` file:

1. **Read the file first** — understand current structure before changing anything
2. **Check page count constraints** — most CVs must be exactly 1 page
3. **Identify which macros are in use** — content is in the `templates/lato/*.tex` files; shared code is in `lato_macros.tex` and `personal_data.tex`
4. **Never duplicate contact info** — only `personal_data.tex` holds it

---

## File Responsibility Map

| Task | File to Edit |
|---|---|
| Change name/email/phone/location | `templates/lato/personal_data.tex` + sync `personal_data.json` |
| Change shared packages/layout/macros | `templates/lato/lato_macros.tex` |
| Edit AI/DS CV content | `templates/lato/CV_AI_Data_Lato.tex` |
| Edit IT/Support CV content | `templates/lato/CV_IT_Infra_Lato.tex` |
| Edit PhD CV content | `templates/lato/CV_PhD_Lato.tex` |
| Add new template | new file in `templates/lato/` + update `scripts/compile.sh` |
| Add job application | new folder `Applied/YYYY-MM_Company_Role/` |

---

## Compile Protocol

**ALWAYS use the compile script:**
```bash
./compile.sh all    # or ai / it / phd
```

This compiles from the correct directory and copies PDFs to `output/`.

**If the script fails**, run manually:
```bash
cd /Users/su6i/@-github/CV/templates/lato
pdflatex -output-directory=/tmp -interaction=nonstopmode CV_AI_Data_Lato.tex
# Check for errors:
grep -E "Output written|^\!" /tmp/CV_AI_Data_Lato.log | head -10
# If success:
cp /tmp/CV_AI_Data_Lato.pdf /Users/su6i/@-github/CV/output/
```

**NEVER compile from `/tmp` with an absolute path** — `\input{lato_macros}` will not resolve.

---

## Academic References

Official diplomas and transcripts are stored in `data/` (gitignored) and optionally mirrored in `.agents/references/` (also gitignored).
- Verifying grade claims before writing them into a CV
- Extracting new grade data for updated CVs
- Confirming degree names and dates

---

## Editing Rules

### Single-page CVs (AI_Data, IT_Infra)
- Must remain exactly **1 page** after every edit
- After any content addition, compile and verify page count
- If it overflows: reduce `\itemspace` first (e.g., `0.15em`), then trim content

### Multi-page CV (PhD)
- No page limit, but keep content dense and professional
- Currently ~4 pages

### Latin characters only
- Run after editing: `perl -ne 'print "$ARGV:$.: $_" if /[^\x00-\x7f]/' templates/lato/*.tex`
- Fix any non-ASCII character before committing

### Formatting consistency
- Section headers: `\cvsection{Name}`
- Job/project headers: `\headerrow{\textbf{Company}, \emph{Role}}{Date}`
- Bullet lists: `\begin{itemize}[leftmargin=1.5em, label={\textbullet}, nosep]`
- Tech stacks: placed as last bullet in italic: `\item \emph{Python, FastAPI, ...}`
- Between items in the same section: `\itemspace`

---

## Content Accuracy Constraints

The following facts are verified and must not be changed without user confirmation:

| Fact | Value |
|---|---|
| toHero internship speed gain | +500% |
| toHero cost reduction | -99% |
| toHero Excel rows processed | 18,000+ |
| toHero PDF pages processed | 1,772 |
| toHero test scenarios | 476 |
| NIOC manual work reduction | -70% |
| NIOC switch count | 70 Cisco 2960 |
| NIOC site visit reduction | -70% |
| Master's Réseaux Avancés grade | 16.33/20 (1st/13) |
| Master's Web Avancé grade | 17.15/20 (2nd/17) |
| Master's Système grade | 16.5/20 |
| VPS provider | Hetzner |
| Image gen API | fal.ai (Flux Schnell) |
| LLM fallback layers | 8 (Gemini/DeepSeek/Grok) |
| Embeddings model | BGE-M3 |
| Vector DB | ChromaDB |

---

## Git Commit Protocol

**There is a pre-commit hook that BLOCKS direct commits to `main`.**  
Always work on a feature branch:

```bash
git checkout -b feature/describe-your-change
# ... make changes and compile ...
git add templates/lato/CV_AI_Data_Lato.tex output/CV_AI_Data_Lato.pdf
git commit -m "cv: update Su6i-Yar with MiniMax 2.5 and fal.ai details"
git checkout main
git merge feature/describe-your-change
```

---

## What NOT to Do

- ❌ Hardcode your real name, email, or phone in `.tex` files — always use `\cvname`, `\cvemail`, `\cvphone` macros from `personal_data.tex`
- ❌ Compile from `/tmp` with an absolute path
- ❌ Leave build artifacts (`.aux`, `.log`, `.fls`) in the repo
- ❌ Modify `lato_macros.tex` without verifying all 3 CVs still compile
- ❌ Change verified metrics (speed, cost, grade numbers) without user instruction
- ❌ Add packages that conflict with `lato` font (`fontspec` requires XeLaTeX)
- ❌ Use `\\[xem]` syntax for vertical space — use `\vspace{xem}` or `\itemspace`

---

## Adding a New Project to a CV

1. Check the page count — if already 1 page, one item must be removed or shortened
2. Use the standard project block:
   ```latex
   \itemspace
   \item
   \headerrow{\textbf{Project Name} | \emph{Personal Project}}{2025}
   \begin{itemize}[leftmargin=1.5em, label=$\bullet$, nosep]
       \item One-line impact sentence with \textbf{metrics}.
       \item \emph{Tech, Stack, Here}
   \end{itemize}
   ```
3. Compile and verify page count

---

## Environment Info

- **TeX engine:** pdflatex (TeX Live 2025)
- **Font:** Lato (`\usepackage[default]{lato}`) — requires `pdflatex`, NOT `xelatex`
- **Path issue:** `@` in the path `/Users/su6i/@-github/` can break some shell piping — always use `cd` first
- **OS:** macOS
