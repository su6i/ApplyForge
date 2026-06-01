# CV Quality Guard: No Persian/Non-Latin Characters

## 🚨 CRITICAL RULE
Any document generated or modified in this repository that is intended for the French market (CVs, Cover Letters, etc.) MUST NOT contain any Persian (Farsi) or non-Latin Unicode characters unless explicitly requested (e.g., in a "Languages" section mention).

## Identification of Remnants
Common dangerous characters that tend to slip in during translation or pasting:
- **و** (and) -> Replace with **et**
- **برای** (for) -> Replace with **pour**
- **با** (with) -> Replace with **avec**
- **در** (in) -> Replace with **dans**

## Enforcement
1. **Automated Check**: Before providing a final PDF or claiming a task is done, run the `src/utils/cv_verify.py` script.
2. **Visual Audit**: Look for characters that don't belong to the French alphabet or standard ASCII.
3. **Grep Check**: Use `perl -ne 'print if /[^\x00-\x7f]/'` to catch any non-standard characters.

## Response style
If a Persian character is found, it is a **CRITICAL FAILURE**. Fix it immediately and recompile all related documents.
