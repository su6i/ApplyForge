# Rule: Never track personal session logs / task lists in git

## Why
Files like `SESSION.md`, `TODO.md` (and similar working notes) accumulate **personal data**
— job applications, company names, visa/residency status, career strategy. This repository
is **public**, so committing them risks leaking that data on any future push.

## Rule
- `SESSION.md`, `TODO.md`, and any personal working-notes file **MUST be gitignored** and
  **never committed**. They live on disk for continuity only.
- If such a file was committed by mistake, scrub it from **all** history with `git filter-repo`
  (e.g. `git filter-repo --invert-paths --path SESSION.md --force`) and re-add to `.gitignore`.
- Before any commit, double-check `git status` / `git diff --cached` for personal files.

## Applies to
This project (ApplyForge). Promote to the global agent-constitution if it should apply to all repos.
