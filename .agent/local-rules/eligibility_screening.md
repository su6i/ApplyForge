# Rule: Eligibility criteria — mandatory check before any application

Before generating a CV, **extract these criteria** from the job text and check the blockers.

---

## 1. BLOCKING criteria (stop immediately, no CV generated)

> The *why* (the candidate's personal profile) lives in the vault (rule 035),
> machine-readable: `~/.local/share/agent-projects/applyforge/data/candidate.yaml`
> (committable template: `config/candidate.example.yaml`). Never write it here.

The signal phrases below stay in French **on purpose** — they are matched verbatim
against French-language job postings (they are data, not prose).

| Criterion | Signals in the text |
|---|---|
| **Driving licence B required** | "permis b obligatoire", "permis b exigé", "permis b requis", "permis b indispensable", "permis de conduire obligatoire", "driving license required" |
| **Civil-servant / tenure required** | "être fonctionnaire", "titulaire de la fonction publique", "réservé aux agents titulaires", "fonctionnaire de catégorie", "mutation", "détachement uniquement" |
| **French nationality required** | "nationalité française obligatoire", "réservé aux ressortissants français", "nationalité française exigée", "être de nationalité française" |
| **Secret/Confidential Defence clearance** | "habilitation secret défense", "habilitation confidentiel défense", "secret-défense", "accès à des informations classifiées SECRET" |
| **Experience > 3 years required** | "X ans d'expérience minimum" with X > 3, "expérience confirmée de X ans exigée" |

**Note:** "souhaité", "apprécié", "un plus" = NOT blocking, continue.

---

## 2. Criteria to EXTRACT and DISPLAY (informational, not blocking)

The pipeline must always extract and show these fields so the user can decide:

| Field | What we extract |
|---|---|
| **French level** | Required level (B1, B2, C1, C2, bilingual, native) |
| **English level** | Required level |
| **Other language** | Language + level if mentioned |
| **Education level** | Bac+2 / Bac+3 / Bac+5 / Doctorate |
| **Experience** | Years desired or required |
| **Contract type** | CDI / CDD / Internship / Apprenticeship + duration |
| **Salary** | Index grid, gross salary, or range if mentioned |
| **Remote work** | Yes / No / Partial (X days/week) |
| **Travel** | Frequent / Occasional / Not mentioned |
| **On-call / shifted hours** | Night, weekend, atypical hours — **positive signal**: less French competition |
| **Working time** | 100% / 80% / 50% etc. |
| **Closing date** | Application deadline |
| **Clearance desired** | "souhaitée" or "able to obtain" (not blocking) |
| **Special medical fitness** | Police, SNCF, firefighters — mandatory medical exam |
| **Imposed technologies** | If the offer requires a tech absent from the profile (SAP, COBOL, etc.) |

---

## 3. Expected scraper output format

For each offer, show a synthesis block **before** starting CV generation:

```
══════════════════════════════════════════
ELIGIBILITY CHECK
══════════════════════════════════════════
🚫 Driving licence B : [required ← BLOCKING | desired | not mentioned]
🚫 Civil servant     : [tenure required ← BLOCKING | contractual OK | not mentioned]
🚫 Nationality       : [French required ← BLOCKING | any | not mentioned]
🚫 Clearance         : [Secret Defence ← BLOCKING | desired | not mentioned]
⚠️  Experience        : [X years required | X years desired | not mentioned]
──────────────────────────────────────────
ℹ️  Contract          : [CDI | CDD X months | Internship | Apprenticeship]
ℹ️  Working time      : [100% | 80% | 50%]
ℹ️  Salary            : [grid X | range X–Y€ | not mentioned]
ℹ️  Remote            : [X days/week | no | not mentioned]
✅  On-call/night     : [mentioned = positive signal (less competition) | not mentioned]
ℹ️  Travel            : [frequent | occasional | not mentioned]
ℹ️  French level      : [B2 | C1 | bilingual | not mentioned]
ℹ️  English level     : [B2 | C1 | not mentioned]
ℹ️  Min. education    : [Bac+2 | Bac+5 | not mentioned]
ℹ️  Closing date      : [DD/MM/YYYY | not mentioned]
ℹ️  Imposed tech      : [list | none imposed]
──────────────────────────────────────────
🎯 FIT SCORE          : XX/100
   [≥70 → generate CV | 50-69 → user decision | <50 → not advised]
══════════════════════════════════════════
```

If a 🚫 criterion is BLOCKING → stop and do not generate the CV.
The fit score (`match_score`) is computed by the LLM in `content_tailor.py`.
Ideally computed before full generation so the user decides without wasting time.

---

## 4. Pipeline integration

This check is implemented in `src/pipeline/service.py` (after scraping, before tailor).
Which requirement is disqualifying depends on the candidate profile, read at runtime from
`candidate.yaml` in the vault (rule 035; template `config/candidate.example.yaml`) — never
hardcode the candidate's attributes in code.
