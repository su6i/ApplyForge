# LaTeX Templates — Technical Reference

[Back to README](../README.md) | [Architecture](architecture.md) | [Bot Setup](bot-setup.md) | [Git Workflow](git-workflow.md)

Note: As of the latest pipeline update the CV may be rendered dynamically from
the internal "life-database" JSON profile (`data/resume_profile.json`). The
`init-profile` utility now accepts `.tex`, `.pdf`, and common image formats
(`.jpg`, `.jpeg`, `.png`, `.webp`) — PDFs use `pdfminer.six` for text
extraction and images use `pytesseract` + `Pillow` for OCR. If you only need
the LaTeX path you do not need these extra packages.

## Template Structure

```
templates/
├── lato/                        ← Lato-font CV templates (active)
│   ├── lato_macros.tex          ← shared packages + macros for all lato CVs
│   ├── CV_AI_Data_Lato.tex      ← AI Engineer / Data Scientist (EN)
│   ├── CV_IT_Infra_Lato.tex     ← Support IT & Réseaux (FR)
│   ├── CV_PhD_Lato.tex          ← PhD Applications (EN)
│   └── CV_Modern_Lato.tex       ← generic modern (draft)
│
├── shared/                      ← single source of truth for contact info
│   ├── personal_data.tex        ← \newcommand macros used by all CV templates
│   └── personal_data.json       ← same data for Python/automation
│
├── classic/                     ← older standalone templates (not modular)
└── experimental/                ← AI-generated experiments
```

---

## Minimal CV File Skeleton

```latex
\documentclass[11pt,a4paper]{article}
\input{lato_macros}              % all packages + shared macros
\input{../shared/personal_data}  % \cvname, \cvemail, \cvphone, …

% Optional per-file overrides:
\renewcommand{\itemspace}{\vspace{0.15em}}

\begin{document}
\cvheader{Job Title Here}

\cvsection{Profile}
One-paragraph summary.

\cvsection{Technical Skills}
\begin{itemize}[leftmargin=*]
  \item \textbf{Category:} skill1, skill2
\end{itemize}

\cvsection{Professional Experience}
\headerrow{\textbf{Company} — Role}{City \textbar{} Date–Date}
\begin{itemize}[leftmargin=*]
  \item Achievement with metric.
\end{itemize}

\end{document}
```

---

## Macros Reference

### Layout macros (from `lato_macros.tex`)

| Macro | Where to use | Effect |
|---|---|---|
| `\cvheader{Job Title}` | First line of `\begin{document}` | Full header block with name, contact icons, links |
| `\cvsection{Name}` | Between sections | Teal horizontal rule + label + smart vertical spacing |
| `\headerrow{Left}{Right}` | Inside `itemize`, one per position | Flush company name left, date right |
| `\itemspace` | Between `\item` groups | `\vspace{0.2em}` — override per file |
| `\sectionspace` | Injected automatically by `\cvsection` | `\vfill` — distributes whitespace evenly across the page |

### Personal data macros (from `personal_data.tex`)

| Macro | What it holds |
|---|---|
| `\cvname` | Full name |
| `\cvlocation` | City, Country |
| `\cvmobility` | Mobility statement (EN) |
| `\cvmobilityFR` | Mobility statement (FR) |
| `\cvemail` | Email address |
| `\cvphone` | Phone number |
| `\cvlinkedin` | LinkedIn URL slug |
| `\cvgithub` | GitHub username |

**Never hardcode these values** directly in a `.tex` file — always define them in `templates/shared/personal_data.tex` and use the macro. This way a single edit updates every CV at once.

---

## Education & Credentials: DU Completion Markers

All CV templates now explicitly mark the completion status of the **Diplôme d'Université (DU)** in Big Data & Data Science to avoid recruiter confusion:

**English templates:** Added "completed a" before DU references
```
Example: "and having completed a DU in Big Data & Data Science"
```

**French templates:** Added "(obtenu)" marker after DU references
```
Example: "DU Big Data & Data Science (obtenu)"
```

**Applied in:**
- `templates/lato/CV_AI_Data_Lato.tex` — profile and education sections
- `templates/lato/CV_IT_Infra_Lato.tex` — profile and education sections
- `templates/lato/CV_PhD_Lato.tex` — education section
- `templates/classic/*.tex` (~20 files) — batch updated via regex
- `cover_letters/Cover_Letter_Template_Fr.tex` — both AI and IT variants
- `cover_letters/Cover_Letter_Template_En.tex` — both AI and Python variants

This ensures generated applications reflect credential status accurately across all roles and languages.

---

## Spacing System

| Variable | Default | Override example | When |
|---|---|---|---|
| `\itemspace` | `\vspace{0.2em}` | `\vspace{0.15em}` | Page slightly over 1 page |
| `\sectionspace` | `\vfill` | — never change | Distributes whitespace evenly |
| First section gap | `\vspace{0.25em}` | — controlled by `\iffirstsection` | Prevents large gap above Profile |
| `geometry` | top/bot `0.3in`, lr `0.4in` | Widen to `0.45in` | Only when content is very sparse |

**Overflow fix order:**
1. Reduce `\itemspace` (e.g. `\vspace{0.1em}`)
2. Remove the least-impactful bullet point
3. Tighten geometry margins

---

## Hyperlinks

`lato_macros.tex` loads `hyperref [hidelinks]`.
- Links are invisible in print but clickable.
- `\cvheader{}` wraps email with `mailto:`, LinkedIn/GitHub with `https://`.
- ATS systems can follow the links.

---

## Adding a New Template Style

Each visual style (different fonts, colours, layout) gets its own folder under `templates/`.

```bash
mkdir templates/banking
```

1. Create `templates/banking/banking_macros.tex`:
   ```latex
   % Load your style-specific packages here
   \usepackage[a4paper, ...]{geometry}
   % … fonts, colors, macros …
   ```

2. Create `templates/banking/CV_Banking.tex`:
   ```latex
   \documentclass[11pt,a4paper]{article}
   \input{banking_macros}
   \input{../shared/personal_data}   % reuse contact info

   \begin{document}
   \cvheader{Analyste Quantitatif}
   % … content …
   \end{document}
   ```

3. Compile — `compile.sh` auto-discovers all `CV_*.tex` under `templates/`:
   ```bash
   ./compile.sh CV_Banking    # just this one
   ./compile.sh all           # rebuilds all templates
   ```

---

## Cover Letter Templates

Located in `cover_letters/`. Two templates cover all cases:

| File | Language | Variants |
|---|---|---|
| `Cover_Letter_Template_Fr.tex` | French | `ai`, `it` |
| `Cover_Letter_Template_En.tex` | English | `ai`, `python` |

Each template has **4 mandatory `\newcommand` variables** at the top:

```latex
\newcommand{\CompanyName}{Capgemini}
\newcommand{\PositionTitle}{Ingénieur Data / IA}
\newcommand{\Variant}{ai}
\newcommand{\WhyThisCompany}{Votre engagement …}
```

The letter body (stock paragraphs) lives in `\ifthenelse{\equal{\Variant}{ai}}{…}{…}` blocks —
**never edit the body**. Only the 4 variables change per application.

Compile with `xelatex` (requires `fontspec` + Times New Roman):
```bash
cd cover_letters
xelatex -interaction=nonstopmode Cover_Letter_Template_Fr.tex
```

---

## Troubleshooting

### `lato_macros.tex not found`
You ran pdflatex from the wrong directory.
Always use `./compile.sh` from the repo root, or `cd templates/lato` first.

### Persistent cached error
```bash
cd templates/lato
latexmk -C CV_IT_Infra_Lato.tex
./compile.sh it
```

### PDF is 2 pages
1. Reduce `\itemspace` → `\vspace{0.1em}`
2. Remove one bullet point
3. Tighten margins slightly

### `Overfull \hbox` warnings
Handled automatically by `\setlength{\emergencystretch}{3em}` in `lato_macros.tex`.
If still visible, add `\raggedright` around the long line.

### `xelatex: Times New Roman not found`
Install the font on macOS:
```bash
# Times New Roman comes with Microsoft Office; alternatively:
brew install --cask font-times-new-roman   # if available
# or use a free substitute in the .tex file:
\setmainfont{TeX Gyre Termes}
```
