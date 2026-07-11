# Quality Guard: one target language per generated document

> Single source of truth for the language rule (rule 045). Other files point here.

## Rule

Every generated document (CV, cover letter, …) must be written in **exactly one
language — its target language** (the language the CV itself is written in). No other
language may be mixed in: a French CV must contain no English, German, Italian, or
Persian text, and the same holds for every target language. The only exception is a
language's own name where it is the subject — e.g. listing "Persian" or "Anglais" in
the Languages section.

This is stricter than "no Persian": it forbids **any** foreign-language leftover, in any
script. It usually appears as an untranslated source word (a Persian conjunction, or an
English word left in a French CV) that slips in during translation or copy-paste.

## Enforcement (before every commit / before delivering a PDF)

1. **Automated check**: run the project's CV verifier (`src/utils/cv_verify.py` /
   `verify.py`) before providing a final PDF or claiming the task done.
2. **Non-Latin scan** (catches Persian/Arabic and other non-Latin scripts in a
   Latin-market CV):
   ```bash
   perl -ne 'print "$ARGV:$.: $_" if /[^\x00-\x7f]/' templates/**/*.tex
   ```
   Review every hit: accented French/Spanish/German letters are legitimate; any
   Arabic-script (Persian) character is a defect.
3. **Same-script leftovers** (e.g. an English word left in a French CV) are not caught
   by the byte scan — verify them in the visual QC pass.

## Response when a leftover is found

It is a **defect**: fix it and recompile the affected documents immediately.
