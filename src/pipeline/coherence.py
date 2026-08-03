"""
coherence.py — Folder-based coherence gate for application bundles.

Verifies that all generated artifacts in an application directory (CV .tex/.pdf,
Cover Letter .tex/.pdf, full .txt, short .txt) tell one consistent story.
Edits to one file trigger detection if sibling artifacts are out-of-date,
contradictory, unsupported, or incomplete.

Layer 1: Deterministic rules R1..R8 (fast, blocking).
Layer 2: Semantic review via agy/Gemini (on by default, --no-semantic to skip;
non-blocking, and skipped automatically when the agy binary is absent).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logger import logger
from src.core.quality_guard import _PERSIAN_RE


@dataclass
class Finding:
    rule: str
    rule_name: str
    severity: str  # "high", "medium", "low"
    source_a: str
    source_b: str
    quote_a: str
    quote_b: str
    message: str


@dataclass
class CoherenceResult:
    application_dir: Path
    findings: list[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Gate passes only when no HIGH severity findings exist."""
        return not any(f.severity.lower() == "high" for f in self.findings)


@dataclass
class DossierArtifacts:
    dir_path: Path
    cv_tex: Path | None = None
    cv_pdf: Path | None = None
    cl_tex: Path | None = None
    cl_pdf: Path | None = None
    cl_full_txt: Path | None = None
    cl_short_txt: Path | None = None
    enclosed_docs: list[tuple[Path, str]] = field(default_factory=list)



# ─── Artifact Discovery & Helper Functions ────────────────────────────────────

def discover_artifacts(dir_path: Path) -> DossierArtifacts:
    """Find the four primary application artifacts plus compiled PDFs in dir_path."""
    artifacts = DossierArtifacts(dir_path=dir_path)
    if not dir_path.exists() or not dir_path.is_dir():
        return artifacts

    for p in dir_path.iterdir():
        if not p.is_file() or p.name.startswith("JobPosting"):
            continue

        name_lower = p.name.lower()
        if p.suffix == ".tex":
            if "cv" in name_lower and not ("lettre" in name_lower or "cover" in name_lower):
                artifacts.cv_tex = p
            elif "lettre" in name_lower or "cover" in name_lower:
                if "_courte_" not in name_lower and "_short_" not in name_lower:
                    artifacts.cl_tex = p
        elif p.suffix == ".pdf":
            if "cv" in name_lower and not ("lettre" in name_lower or "cover" in name_lower):
                artifacts.cv_pdf = p
            elif "lettre" in name_lower or "cover" in name_lower:
                if "_courte_" not in name_lower and "_short_" not in name_lower:
                    artifacts.cl_pdf = p
        elif p.suffix == ".txt":
            if "_courte_" in name_lower or "_short_" in name_lower:
                artifacts.cl_short_txt = p
            elif ("lettre" in name_lower or "cover" in name_lower) and not name_lower.startswith("jobposting"):
                artifacts.cl_full_txt = p

    return artifacts


def _sha256_text(path: Path) -> str:
    """Compute sha256 hash of normalized text content (stripping carriage returns/trailing spaces)."""
    try:
        text = path.read_text(encoding="utf-8")
        norm = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _strip_latex_comments(text: str) -> str:
    """Strip LaTeX comments (unescaped % to end of line)."""
    lines = []
    for line in text.splitlines():
        cleaned = re.sub(r"(?<!\\)(?:\\\\)*%.*", "", line)
        lines.append(cleaned)
    return "\n".join(lines)


def _read_artifact_text(path: Path) -> str:
    """Read artifact text, stripping LaTeX comments if path is a .tex file."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".tex":
        return _strip_latex_comments(text)
    return text


def _extract_education_text(cv_tex: Path) -> str:
    """Extract text inside the CV's Education / Formation section."""
    if not cv_tex or not cv_tex.exists():
        return ""
    text = _read_artifact_text(cv_tex)

    # Locate Education / Formation section
    pattern = r"\\(?:cv)?section\{[^}]*(?:Education|Formation)[^}]*\}(.*?)(?=\\(?:cv)?section|\Z)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    return text  # Fallback to whole text if sections not explicitly marked


def _extract_profile_text(cv_tex: Path) -> str:
    """Extract text inside the CV's Profile / Summary section."""
    if not cv_tex or not cv_tex.exists():
        return ""
    text = _read_artifact_text(cv_tex)

    pattern = r"\\(?:cv)?section\{[^}]*(?:Profile|Profil|Summary|Résumé)[^}]*\}(.*?)(?=\\(?:cv)?section|\Z)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    # Also check \cvprofile or header summary block
    return text[:1000]


# ─── Layer 1 Rules (R1 .. R8) ──────────────────────────────────────────────────

def _check_r1_stale_artifact(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R1 stale-artifact: Every .txt must be at least as new as the .tex it mirrors,
    and .pdf at least as new as its .tex. Hash sidecar .coherence.json tracks
    edits to ensure all artifacts are re-derived together.
    """
    # Timestamp checks
    if artifacts.cl_tex and artifacts.cl_tex.exists():
        tex_mtime = artifacts.cl_tex.stat().st_mtime
        for txt_path, label in [(artifacts.cl_full_txt, "full cover letter .txt"), (artifacts.cl_short_txt, "short cover letter .txt")]:
            if txt_path and txt_path.exists():
                if txt_path.stat().st_mtime < tex_mtime - 0.01:
                    findings.append(Finding(
                        rule="R1",
                        rule_name="stale-artifact",
                        severity="high",
                        source_a=txt_path.name,
                        source_b=artifacts.cl_tex.name,
                        quote_a=f"mtime {txt_path.stat().st_mtime}",
                        quote_b=f"mtime {tex_mtime}",
                        message=f"{label} ({txt_path.name}) is older than the cover letter .tex source",
                    ))

        if artifacts.cl_pdf and artifacts.cl_pdf.exists():
            if artifacts.cl_pdf.stat().st_mtime < tex_mtime - 0.01:
                findings.append(Finding(
                    rule="R1",
                    rule_name="stale-artifact",
                    severity="high",
                    source_a=artifacts.cl_pdf.name,
                    source_b=artifacts.cl_tex.name,
                    quote_a=f"mtime {artifacts.cl_pdf.stat().st_mtime}",
                    quote_b=f"mtime {tex_mtime}",
                    message=f"Cover letter PDF ({artifacts.cl_pdf.name}) is older than its .tex source",
                ))

    if artifacts.cv_tex and artifacts.cv_tex.exists() and artifacts.cv_pdf and artifacts.cv_pdf.exists():
        if artifacts.cv_pdf.stat().st_mtime < artifacts.cv_tex.stat().st_mtime - 0.01:
            findings.append(Finding(
                rule="R1",
                rule_name="stale-artifact",
                severity="high",
                source_a=artifacts.cv_pdf.name,
                source_b=artifacts.cv_tex.name,
                quote_a=f"mtime {artifacts.cv_pdf.stat().st_mtime}",
                quote_b=f"mtime {artifacts.cv_tex.stat().st_mtime}",
                message=f"CV PDF ({artifacts.cv_pdf.name}) is older than its .tex source",
            ))

    # Sidecar .coherence.json hash verification
    sidecar_path = artifacts.dir_path / ".coherence.json"
    if sidecar_path.exists():
        try:
            saved_hashes: dict[str, str] = json.loads(sidecar_path.read_text(encoding="utf-8"))
            current_hashes: dict[str, str] = {}
            for path in [artifacts.cv_tex, artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt]:
                if path and path.exists():
                    current_hashes[path.name] = _sha256_text(path)

            cv_changed = (
                artifacts.cv_tex
                and artifacts.cv_tex.name in saved_hashes
                and current_hashes.get(artifacts.cv_tex.name) != saved_hashes[artifacts.cv_tex.name]
            )
            cl_changed = (
                artifacts.cl_tex
                and artifacts.cl_tex.name in saved_hashes
                and current_hashes.get(artifacts.cl_tex.name) != saved_hashes[artifacts.cl_tex.name]
            )

            if cv_changed and not cl_changed and artifacts.cl_tex:
                findings.append(Finding(
                    rule="R1",
                    rule_name="stale-artifact",
                    severity="high",
                    source_a=artifacts.cv_tex.name,
                    source_b=artifacts.cl_tex.name,
                    quote_a="CV .tex modified",
                    quote_b="Letter .tex unchanged since last check",
                    message="CV was modified but the cover letter was not regenerated/updated",
                ))
            elif cl_changed and not cv_changed and artifacts.cv_tex:
                findings.append(Finding(
                    rule="R1",
                    rule_name="stale-artifact",
                    severity="high",
                    source_a=artifacts.cl_tex.name,
                    source_b=artifacts.cv_tex.name,
                    quote_a="Letter .tex modified",
                    quote_b="CV .tex unchanged since last check",
                    message="Cover letter was modified but the CV was not re-reviewed/updated",
                ))
        except Exception as exc:
            logger.warning(f"Could not read sidecar .coherence.json: {exc}")


def _discover_enclosed_docs(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    Find and extract text from enclosed supporting documents (e.g. reference letters,
    files in context/ subfolder) to extend the evidence corpus.
    Emits an INFO-level finding if an enclosed PDF cannot be text-extracted.
    """
    primary_paths = {
        p.resolve()
        for p in [
            artifacts.cv_tex,
            artifacts.cv_pdf,
            artifacts.cl_tex,
            artifacts.cl_pdf,
            artifacts.cl_full_txt,
            artifacts.cl_short_txt,
        ]
        if p and p.exists()
    }

    candidates: list[Path] = []
    for p in artifacts.dir_path.rglob("*"):
        if not p.is_file():
            continue
        if p.resolve() in primary_paths:
            continue
        if p.name in ("COHERENCE.md", ".coherence.json", ".DS_Store"):
            continue
        if p.name.startswith("."):
            continue
        if p.name.startswith("JobPosting"):
            continue
        candidates.append(p)

    for p in candidates:
        suf = p.suffix.lower()
        if suf in (".txt", ".md", ".tex"):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                if text.strip():
                    artifacts.enclosed_docs.append((p, text))
            except Exception:
                pass
        elif suf == ".pdf":
            try:
                from pdfminer.high_level import extract_text as pdf_extract_text
                pdf_text = pdf_extract_text(str(p))
                if pdf_text and pdf_text.strip():
                    artifacts.enclosed_docs.append((p, pdf_text))
                else:
                    findings.append(Finding(
                        rule="R0",
                        rule_name="unextractable-pdf",
                        severity="info",
                        source_a=p.name,
                        source_b="",
                        quote_a="",
                        quote_b="",
                        message=f"Could not extract text from enclosed PDF {p.name}",
                    ))
            except Exception as exc:
                findings.append(Finding(
                    rule="R0",
                    rule_name="unextractable-pdf",
                    severity="info",
                    source_a=p.name,
                    source_b="",
                    quote_a="",
                    quote_b="",
                    message=f"Could not extract text from enclosed PDF {p.name}: {exc}",
                ))


def _is_kw_in_text(kw: str, text: str) -> bool:
    if kw == "DU":
        return bool(re.search(r"(?<!\w)DU(?!\w)", text))
    pattern = r"(?<!\w)" + re.escape(kw) + r"(?!\w)"
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def _is_applied_for_position(text: str, start_idx: int, end_idx: int) -> bool:
    """
    Determine if a diploma match at (start_idx, end_idx) in text refers to an
    applied-for position (future/conditional/candidature) rather than a claimed credential.
    """
    line_start = text.rfind("\n", 0, start_idx)
    line_start = 0 if line_start == -1 else line_start + 1
    line_end = text.find("\n", end_idx)
    line_end = len(text) if line_end == -1 else line_end
    line = text[line_start:line_end].strip()

    if re.search(r"^\s*(?:Objet|Subject)\s*:", line, re.IGNORECASE):
        return True

    claim_window = text[max(0, start_idx - 150):end_idx].lower()
    if re.search(r"\b(?:titulaire|obtenu|obtained|graduated|diplômé|diplome|holding|completed)\b", claim_window):
        return False

    win_start = max(0, start_idx - 70)
    win_end = min(len(text), end_idx + 70)
    window = text[win_start:win_end].lower()

    applied_patterns = [
        r"\bcandidat\w*",
        r"\bpostul\w*",
        r"\bapply\w*",
        r"\bapplication\b",
        r"\bposte\s+de\b",
        r"\bposition\b",
        r"\bsujet\s+de\b",
        r"\boffre\s+de\b",
        r"\bprojet\s+de\b",
        r"\bcontrat\s+doctoral\b",
        r"\bthèse\s+de\b",
        r"\bpoursuivre\b",
        r"\bentreprendre\b",
        r"\bpréparer\b|\bpreparer\b",
        r"\bréaliser\b|\brealiser\b",
        r"\benvisage\b",
        r"\bsouhaite\b",
        r"\bseeking\b",
        r"\bpursue\b",
        r"\bprospective\b",
        r"\bfellowship\b",
        r"\bvacancy\b",
        r"\bopening\b",
    ]

    for pat in applied_patterns:
        if re.search(pat, window):
            return True

    return False


def _check_r2_diploma_support(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R2 diploma-support: Every diploma named in the letter (either .txt or .tex)
    must appear in the CV's FORMATION section or enclosed supporting documents.
    """
    if not artifacts.cv_tex or not artifacts.cv_tex.exists():
        return

    edu_text = _extract_education_text(artifacts.cv_tex)

    label_keywords = {
        "DU": ["DU", "D.U.", "d.u.", "diplôme universitaire", "diplome universitaire", "diplôme d'université", "diplome d'universite"],
        "Master": ["master", "msc", "bac+5"],
        "Licence": ["licence", "bachelor", "bsc", "bac+3"],
        "Doctorat/PhD": ["doctorat", "phd", "ph.d."],
        "Ingénieur": ["ingénieur", "ingenieur"],
        "BTS": ["bts"],
        "DUT": ["dut"],
    }

    diploma_patterns: list[tuple[str, str, bool]] = [
        (r"(?<!\w)DU(?!\w)", "DU", True),
        (r"\bD\.U\.\b|\bDipl[ôo]me\s+Universitaire\b|\bDipl[ôo]me\s+d['’]Universit[ée]\b", "DU", False),
        (r"\bMaster\b|\bMSc\b|\bBac\+5\b", "Master", False),
        (r"\bLicence\b|\bBachelor\b|\bBSc\b|\bBac\+3\b", "Licence", False),
        (r"\bDoctorat\b|\bPhD\b|\bPh\.D\.\b", "Doctorat/PhD", False),
        (r"\bIngénieur\b|\bIngenieur\b", "Ingénieur", False),
        (r"\bBTS\b", "BTS", False),
        (r"\bDUT\b", "DUT", False),
    ]

    letter_paths = [p for p in [artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt] if p and p.exists()]
    checked_diplomas: set[str] = set()

    for path in letter_paths:
        text = _read_artifact_text(path)
        for pattern, label, is_case_sensitive in diploma_patterns:
            flags = 0 if is_case_sensitive else re.IGNORECASE
            matches = re.finditer(pattern, text, flags=flags)
            for m in matches:
                if _is_applied_for_position(text, m.start(), m.end()):
                    continue

                start = max(0, m.start() - 10)
                end = min(len(text), m.end() + 30)
                context_phrase = text[start:end].replace("\n", " ").strip()
                diploma_key = f"{label}:{m.group(0).lower()}"

                if diploma_key in checked_diplomas:
                    continue
                checked_diplomas.add(diploma_key)

                kw_list = label_keywords.get(label, [label.lower()])
                in_edu = any(_is_kw_in_text(kw, edu_text) for kw in kw_list)
                in_enclosed = any(
                    any(_is_kw_in_text(kw, doc_text) for kw in kw_list)
                    for _, doc_text in artifacts.enclosed_docs
                )
                if not (in_edu or in_enclosed):
                    findings.append(Finding(
                        rule="R2",
                        rule_name="diploma-support",
                        severity="high",
                        source_a=path.name,
                        source_b=artifacts.cv_tex.name,
                        quote_a=context_phrase,
                        quote_b=edu_text[:200],
                        message=f"Diploma '{label}' mentioned in letter ({path.name}) does not appear in CV FORMATION section or enclosed supporting documents",
                    ))


def _check_r3_diploma_contradiction(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R3 diploma-contradiction: The letter may not assert a highest degree / initial
    formation that the CV contradicts, nor omit a diploma central to the CV profile.
    """
    if not artifacts.cv_tex or not artifacts.cv_tex.exists():
        return

    profile_text = _extract_profile_text(artifacts.cv_tex)
    profile_lc = profile_text.lower()
    letter_paths = [p for p in [artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt] if p and p.exists()]

    # If CV profile presents DU Big Data as central, letter must not omit it or claim contradicting primary degree
    if ("du big data" in profile_lc or "diplôme universitaire" in profile_lc) and "master" not in profile_lc:
        for path in letter_paths:
            text = _read_artifact_text(path)
            text_lc = text.lower()
            if "master" in text_lc and "du" not in text_lc and "diplôme universitaire" not in text_lc:
                findings.append(Finding(
                    rule="R3",
                    rule_name="diploma-contradiction",
                    severity="high",
                    source_a=path.name,
                    source_b=artifacts.cv_tex.name,
                    quote_a="Letter frames primary degree as Master without DU",
                    quote_b=profile_text[:200],
                    message=f"Letter ({path.name}) asserts Master framing contradicted by CV profile focusing on DU",
                ))


def _strip_identifiers(text: str) -> str:
    """Strip ORCIDs and phone numbers structurally from text so they are not extracted as metrics."""
    # Mask ORCID: 0000-0002-1825-0097 or https://orcid.org/...
    text = re.sub(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b", lambda m: " " * len(m.group(0)), text)
    # Mask \cvphone{...}
    text = re.sub(r"\\cvphone\{[^}]*\}", lambda m: " " * len(m.group(0)), text)

    # Mask standalone phone numbers (starting with + or 0, containing 9-15 digits total)
    def _replace_phone(m: re.Match) -> str:
        raw = m.group(0)
        digits = re.sub(r"\D", "", raw)
        if 9 <= len(digits) <= 15:
            return " " * len(raw)
        return raw

    phone_pattern = r"(?:\+\d{1,4}|\b0\d)(?:[\s\.\-\(\)]*\d){7,13}\b"
    text = re.sub(phone_pattern, _replace_phone, text)
    return text


def _normalize_latex_numbers(text: str) -> str:
    r"""Normalize LaTeX numeric decorations ({,}, \, ~, \%) before metric comparison."""
    text = text.replace("{,}", ",")
    text = text.replace(r"\,", " ")
    text = text.replace(r"\~", " ").replace("~", " ")
    text = text.replace(r"\%", "%")
    return text


def _check_r4_metric_support(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R4 metric-support: Every metric in the letter or .txt must occur in the CV
    or enclosed supporting documents with the same subject noun within a short context window.
    """
    if not artifacts.cv_tex or not artifacts.cv_tex.exists():
        return

    cv_text = _normalize_latex_numbers(_strip_identifiers(_read_artifact_text(artifacts.cv_tex)))

    letter_paths = [p for p in [artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt] if p and p.exists()]

    for path in letter_paths:
        raw_text = _read_artifact_text(path)
        text = _normalize_latex_numbers(_strip_identifiers(raw_text))

        # Find explicit numeric figures (> 10, skipping years like 2020..2030)
        for m in re.finditer(r"\b(\d{1,3}(?:[\s\.,]\d{1,3})+|\d{2,4}\+?)\b", text):
            val_raw = m.group(0).strip()
            val_clean = re.sub(r"[\s\.,\+]", "", val_raw)
            if not val_clean.isdigit():
                continue
            num_val = int(val_clean)
            if 2020 <= num_val <= 2030:
                continue  # Skip calendar years

            # Extract window around metric in letter
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            letter_window = text[start:end].replace("\n", " ").strip()

            # Check if this metric exists in CV or in enclosed supporting documents
            cv_has_metric = False
            cv_window = ""

            # 1. Search CV
            for cv_m in re.finditer(r"\b(\d{1,3}(?:[\s\.,]\d{1,3})+|\d{2,4}\+?)\b", cv_text):
                cv_raw = cv_m.group(0).strip()
                cv_clean = re.sub(r"[\s\.,\+]", "", cv_raw)
                if cv_clean == val_clean:
                    cv_has_metric = True
                    cv_start = max(0, cv_m.start() - 50)
                    cv_end = min(len(cv_text), cv_m.end() + 50)
                    cv_window = cv_text[cv_start:cv_end].replace("\n", " ").strip()
                    break

            # 2. Search enclosed documents if not found in CV
            if not cv_has_metric:
                for _, doc_raw in artifacts.enclosed_docs:
                    doc_text = _normalize_latex_numbers(_strip_identifiers(doc_raw))
                    for doc_m in re.finditer(r"\b(\d{1,3}(?:[\s\.,]\d{1,3})+|\d{2,4}\+?)\b", doc_text):
                        doc_raw_val = doc_m.group(0).strip()
                        doc_clean = re.sub(r"[\s\.,\+]", "", doc_raw_val)
                        if doc_clean == val_clean:
                            cv_has_metric = True
                            doc_start = max(0, doc_m.start() - 50)
                            doc_end = min(len(doc_text), doc_m.end() + 50)
                            cv_window = doc_text[doc_start:doc_end].replace("\n", " ").strip()
                            break
                    if cv_has_metric:
                        break

            if not cv_has_metric:
                findings.append(Finding(
                    rule="R4",
                    rule_name="metric-support",
                    severity="high",
                    source_a=path.name,
                    source_b=artifacts.cv_tex.name,
                    quote_a=letter_window,
                    quote_b="Not found in CV or enclosed supporting documents",
                    message=f"Metric '{val_raw}' in {path.name} is not present in CV or enclosed supporting documents",
                ))
            else:
                # Check subject noun alignment: e.g. Power BI dashboards vs Support N2/N3
                tool_words = ["power bi", "sap", "solarwinds", "crewai", "cisco", "sql"]
                for tool in tool_words:
                    if tool in letter_window.lower() and tool not in cv_window.lower():
                        findings.append(Finding(
                            rule="R4",
                            rule_name="metric-support",
                            severity="high",
                            source_a=path.name,
                            source_b=artifacts.cv_tex.name,
                            quote_a=letter_window,
                            quote_b=cv_window,
                            message=f"Metric '{val_raw}' in {path.name} is attached to '{tool}' which does not match CV context",
                        ))


def _norm_id_val(s: str | None) -> str:
    """Normalize identity value by collapsing whitespace and stripping trailing punctuation."""
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(".,;:")
    return s


def _parse_subject_line(text: str) -> tuple[str | None, str | None]:
    """
    Extract (position_title, company_name) from letter subject line.
    Handles French and English templates:
      FR: "Objet : Candidature au poste de X — Y" or "Objet : Candidature au poste de X"
      EN: "Subject: Application for the X position — Y" or "Subject: Application for X position — Y"
    Splits on the LAST separator ('—', '--', ' - ') between position and company.
    """
    match = re.search(
        r"^\s*(?:Objet|Subject)\s*:\s*(.*)$", text, flags=re.IGNORECASE | re.MULTILINE
    )
    if not match:
        return None, None

    subj_body = match.group(1).strip()

    raw_pos_comp = None
    if re.match(r"^Candidature au poste de\s+", subj_body, re.IGNORECASE):
        raw_pos_comp = re.sub(r"^Candidature au poste de\s+", "", subj_body, flags=re.IGNORECASE).strip()
    elif re.match(r"^Application for(?: the)?\s+", subj_body, re.IGNORECASE):
        raw_pos_comp = re.sub(r"^Application for(?: the)?\s+", "", subj_body, flags=re.IGNORECASE).strip()
    else:
        raw_pos_comp = subj_body

    if not raw_pos_comp:
        return None, None

    pos: str | None = None
    comp: str | None = None

    if "—" in raw_pos_comp:
        parts = raw_pos_comp.rsplit("—", 1)
        pos, comp = parts[0].strip(), parts[1].strip()
    elif " -- " in raw_pos_comp:
        parts = raw_pos_comp.rsplit(" -- ", 1)
        pos, comp = parts[0].strip(), parts[1].strip()

    if pos is None:
        pos = raw_pos_comp
        comp = None

    if pos:
        pos = re.sub(r"\s+position$", "", pos, flags=re.IGNORECASE).strip()

    return pos if pos else None, comp if comp else None


def _extract_name_from_txt(text: str) -> str | None:
    """
    Extract candidate name from a .txt artifact.
    Checks header lines (first 5 non-empty lines) and signature block lines (last 5 non-empty lines).
    Returns name string if found, otherwise None.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    def _is_valid_name(line: str) -> bool:
        if not (3 <= len(line) <= 60):
            return False
        if any(c in line for c in "@+0123456789=<>{}[]/\\"):
            return False
        if re.search(r"^(?:Objet|Subject|Madame|Monsieur|Dear|Cordialement|Sincerely|Dans l|Veuillez|Best|Regards|Bien|http|www)", line, re.IGNORECASE):
            return False
        if "," in line or "mobile" in line.lower() or "france" in line.lower():
            return False
        if len(re.findall(r"[a-zA-ZÀ-ÿ]", line)) < 2:
            return False
        return True

    # 1. Check header lines (before subject/salutation)
    for line in lines[:5]:
        if _is_valid_name(line):
            return line

    # 2. Check signature block lines (last 5 non-empty lines)
    for line in reversed(lines[-5:]):
        if _is_valid_name(line):
            return line

    return None


def _check_r5_identity(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R5 identity: Company name, position title, candidate name, phone, e-mail,
    and city must be byte-identical across all four artifacts.
    """
    identities: dict[str, dict[str, str]] = {}

    for path in [artifacts.cv_tex, artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt]:
        if not path or not path.exists():
            continue
        text = _read_artifact_text(path)
        id_data: dict[str, str] = {}

        if path.suffix == ".tex":
            m_comp = re.search(r"\\(?:newcommand|providecommand)\{\\CompanyName\}\{([^}]*)\}", text)
            if m_comp:
                id_data["company"] = _norm_id_val(m_comp.group(1))

            m_title = re.search(r"\\(?:newcommand|providecommand)\{\\PositionTitle\}\{([^}]*)\}", text)
            if m_title:
                id_data["position"] = _norm_id_val(m_title.group(1))

            m_name = re.search(r"\\(?:newcommand\{)?\\cvname\}?\{([^}]*)\}", text)
            if m_name:
                id_data["name"] = _norm_id_val(m_name.group(1))

            m_phone = re.search(r"\\(?:newcommand\{)?\\cvphone\}?\{([^}]*)\}", text)
            if m_phone:
                id_data["phone"] = _norm_id_val(m_phone.group(1))

            m_email = re.search(r"\\(?:newcommand\{)?\\cvemail\}?\{([^}]*)\}", text)
            if m_email:
                id_data["email"] = _norm_id_val(m_email.group(1))

            m_city = re.search(r"\\(?:re)?new-?command\{\\cvlocation\}\{([^}]*)\}", text)
            if m_city:
                id_data["city"] = _norm_id_val(m_city.group(1).split(",")[0])

            # If position or company not set by macro in .tex, check subject line in .tex
            if "position" not in id_data or "company" not in id_data:
                pos_subj, comp_subj = _parse_subject_line(text)
                if "position" not in id_data and pos_subj:
                    id_data["position"] = _norm_id_val(pos_subj)
                if "company" not in id_data and comp_subj:
                    id_data["company"] = _norm_id_val(comp_subj)
        else:  # .txt
            pos_subj, comp_subj = _parse_subject_line(text)
            if pos_subj:
                id_data["position"] = _norm_id_val(pos_subj)
            if comp_subj:
                id_data["company"] = _norm_id_val(comp_subj)

            name = _extract_name_from_txt(text)
            if name:
                id_data["name"] = _norm_id_val(name)

            lines = [line.strip() for line in text.splitlines() if line.strip()]
            for line in lines:
                m_em = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", line)
                if m_em and "email" not in id_data:
                    id_data["email"] = _norm_id_val(m_em.group(0))

                m_ph = re.search(r"\+?\d[\d\s\.\-]{7,}\d", line)
                if m_ph and "phone" not in id_data and not line.startswith("Objet") and not line.startswith("Subject"):
                    id_data["phone"] = _norm_id_val(m_ph.group(0))

        identities[path.name] = id_data

    # Compare key fields across artifacts
    field_labels = ["company", "position", "name", "phone", "email"]
    for f_key in field_labels:
        values = {name: data[f_key] for name, data in identities.items() if f_key in data and data[f_key]}
        unique_vals = set(values.values())
        if len(unique_vals) > 1:
            items = list(values.items())
            src_a, val_a = items[0]
            src_b, val_b = next((s, v) for s, v in items if v != val_a)
            findings.append(Finding(
                rule="R5",
                rule_name="identity",
                severity="high",
                source_a=src_a,
                source_b=src_b,
                quote_a=f"{f_key}='{val_a}'",
                quote_b=f"{f_key}='{val_b}'",
                message=f"Identity mismatch for '{f_key}' between {src_a} and {src_b}",
            ))


def _check_r6_completeness(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R6 completeness: CV .tex+.pdf, letter .tex+.pdf, full letter .txt, short letter .txt
    all present. Short .txt <= 1500 chars. Every .txt must contain subject, salutation, signature.
    """
    required = [
        ("CV .tex", artifacts.cv_tex),
        ("CV .pdf", artifacts.cv_pdf),
        ("Cover letter .tex", artifacts.cl_tex),
        ("Cover letter .pdf", artifacts.cl_pdf),
        ("Full cover letter .txt", artifacts.cl_full_txt),
        ("Short cover letter .txt", artifacts.cl_short_txt),
    ]

    for label, path in required:
        if not path or not path.exists():
            findings.append(Finding(
                rule="R6",
                rule_name="completeness",
                severity="high",
                source_a=label,
                source_b="",
                quote_a="Missing",
                quote_b="",
                message=f"Required dossier artifact missing: {label}",
            ))

    if artifacts.cl_short_txt and artifacts.cl_short_txt.exists():
        text = artifacts.cl_short_txt.read_text(encoding="utf-8")
        if len(text) > 1500:
            findings.append(Finding(
                rule="R6",
                rule_name="completeness",
                severity="high",
                source_a=artifacts.cl_short_txt.name,
                source_b="",
                quote_a=f"Length: {len(text)} chars",
                quote_b="Limit: 1500 chars",
                message=f"Short cover letter exceeds character limit ({len(text)} > 1500)",
            ))

    for txt_path in [artifacts.cl_full_txt, artifacts.cl_short_txt]:
        if txt_path and txt_path.exists():
            content = txt_path.read_text(encoding="utf-8")
            has_subj = bool(re.search(r"Objet\s*:|Subject\s*:", content, re.IGNORECASE))
            has_salut = bool(re.search(r"Madame,\s*Monsieur|Dear\s+", content, re.IGNORECASE))
            lines = [line_str.strip() for line_str in content.splitlines() if line_str.strip()]
            has_sig = len(lines) >= 3

            if not (has_subj and has_salut and has_sig):
                findings.append(Finding(
                    rule="R6",
                    rule_name="completeness",
                    severity="high",
                    source_a=txt_path.name,
                    source_b="",
                    quote_a=content[:100],
                    quote_b="",
                    message=f"Letter text file ({txt_path.name}) is missing required structure (subject, salutation, signature)",
                ))


def _check_r7_language(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R7 language: One language per dossier; no stray English in an fr dossier and vice versa.
    """
    for path in [artifacts.cv_tex, artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt]:
        if not path or not path.exists():
            continue

        text = _read_artifact_text(path)
        is_fr = "_fr" in path.name.lower() or "madame, monsieur" in text.lower() or "objet :" in text.lower()
        is_en = "_en" in path.name.lower() or "dear hiring manager" in text.lower() or "subject:" in text.lower()

        if is_fr:
            for stray in ["Dear Hiring Manager", "Sincerely,"]:
                if stray.lower() in text.lower():
                    findings.append(Finding(
                        rule="R7",
                        rule_name="language",
                        severity="medium",
                        source_a=path.name,
                        source_b="",
                        quote_a=stray,
                        quote_b="",
                        message=f"Stray English text '{stray}' found in French artifact {path.name}",
                    ))
        elif is_en:
            for stray in ["Madame, Monsieur", "Lettre de motivation"]:
                if stray.lower() in text.lower():
                    findings.append(Finding(
                        rule="R7",
                        rule_name="language",
                        severity="medium",
                        source_a=path.name,
                        source_b="",
                        quote_a=stray,
                        quote_b="",
                        message=f"Stray French text '{stray}' found in English artifact {path.name}",
                    ))

        # Check Persian / Arabic characters
        for i, line in enumerate(text.splitlines(), 1):
            if _PERSIAN_RE.search(line):
                findings.append(Finding(
                    rule="R7",
                    rule_name="language",
                    severity="high",
                    source_a=path.name,
                    source_b="",
                    quote_a=line.strip()[:60],
                    quote_b="",
                    message=f"Persian/Arabic characters detected on line {i} in {path.name}",
                ))


def _check_r8_no_placeholder(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R8 no-placeholder: No [...], Company Name, City Name, Unknown Company, REDACTED-
    in any artifact.
    """
    patterns = [
        (r"\[\s*\.\.\.\s*\]", "[...]"),
        (r"\[?\bCompany\s+Name\b\]?", "Company Name"),
        (r"\[?\bCity\s+Name\b\]?", "City Name"),
        (r"\[?\bUnknown\s+Company\b\]?", "Unknown Company"),
        (r"REDACTED-", "REDACTED-"),
        (r"\[Insert\s+[^\]]+\]", "[Insert ...]"),
        (r"XXX{2,}", "XXX"),
        (r"\?{3,}", "???"),
    ]

    for path in [artifacts.cv_tex, artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt]:
        if not path or not path.exists():
            continue
        text = _read_artifact_text(path)
        for pat, label in patterns:
            match = re.search(pat, text, flags=re.IGNORECASE)
            if match:
                findings.append(Finding(
                    rule="R8",
                    rule_name="no-placeholder",
                    severity="high",
                    source_a=path.name,
                    source_b="",
                    quote_a=match.group(0),
                    quote_b="",
                    message=f"Unfilled placeholder '{match.group(0)}' found in {path.name}",
                ))


# ─── Layer 2 Semantic Review ──────────────────────────────────────────────────

def _semantic_unavailable(findings: list[Finding], why: str) -> None:
    """
    Record that Layer 2 could not run. Layer 2 is on by default, so a silent
    skip would read exactly like a clean semantic review — the gate would
    hand back false confidence on the one layer that catches wording drift.
    """
    logger.warning(f"Layer 2 semantic review unavailable: {why}")
    findings.append(Finding(
        rule="L2-semantic",
        rule_name="semantic-unavailable",
        severity="low",
        source_a="",
        source_b="",
        quote_a=why,
        quote_b="",
        message="Layer 2 semantic review did not run — Layer 1 rules only",
    ))


def _run_semantic_pass(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    Layer 2: LLM semantic review using agy CLI with gemini-3.6-flash-low model.
    On by default; records a LOW finding rather than passing silently when it
    cannot run.
    """
    if not shutil.which("agy"):
        _semantic_unavailable(findings, "agy binary not found in PATH")
        return

    corpus: list[str] = []
    for p in [artifacts.cv_tex, artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt]:
        if p and p.exists():
            corpus.append(f"--- ARTIFACT: {p.name} ---\n" + _read_artifact_text(p))

    if not corpus:
        return

    full_text = "\n\n".join(corpus)
    schema = {
        "type": "object",
        "properties": {
            "contradictions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_a": {"type": "string"},
                        "source_a": {"type": "string"},
                        "claim_b": {"type": "string"},
                        "source_b": {"type": "string"},
                        "severity": {"type": "string", "enum": ["high", "medium", "low"]}
                    },
                    "required": ["claim_a", "source_a", "claim_b", "source_b", "severity"]
                }
            },
            "unsupported_claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "source": {"type": "string"},
                        "why": {"type": "string"}
                    },
                    "required": ["claim", "source", "why"]
                }
            },
            "narrative_drift": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "issue": {"type": "string"},
                        "sources": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["issue", "sources"]
                }
            }
        },
        "required": ["contradictions", "unsupported_claims", "narrative_drift"]
    }

    prompt = (
        "Report ONLY factual conflicts, unsupported claims, or narrative drift BETWEEN "
        "the supplied artifacts. Do not judge style. Do not suggest rewrites.\n\n"
        + full_text
    )

    # agy contract (verified against the CLI, 2026-08-03): the prompt goes behind
    # -p, --json-schema takes a FILE PATH and is rejected unless --output-format
    # is json, and the parsed payload comes back under "structured_output" — not
    # at the top level, which is where this used to look.
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(schema, fh)
            schema_path = fh.name
        try:
            cmd = [
                "agy", "-p", prompt,
                "--model", "gemini-3.6-flash-low",
                "--output-format", "json",
                "--json-schema", schema_path,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        finally:
            Path(schema_path).unlink(missing_ok=True)

        if res.returncode != 0 or not res.stdout.strip():
            _semantic_unavailable(
                findings,
                f"agy exited {res.returncode}: {(res.stderr or res.stdout).strip()[:200]}",
            )
        else:
            envelope = json.loads(res.stdout)
            if envelope.get("status") != "SUCCESS":
                _semantic_unavailable(findings, f"agy status={envelope.get('status')}")
                return
            data = envelope.get("structured_output") or {}
            for c in data.get("contradictions", []):
                findings.append(Finding(
                    rule="L2-semantic",
                    rule_name="semantic-contradiction",
                    severity=c.get("severity", "medium"),
                    source_a=c.get("source_a", ""),
                    source_b=c.get("source_b", ""),
                    quote_a=c.get("claim_a", ""),
                    quote_b=c.get("claim_b", ""),
                    message="Semantic contradiction detected by LLM",
                ))
            for u in data.get("unsupported_claims", []):
                findings.append(Finding(
                    rule="L2-semantic",
                    rule_name="semantic-unsupported-claim",
                    severity="medium",
                    source_a=u.get("source", ""),
                    source_b="",
                    quote_a=u.get("claim", ""),
                    quote_b=u.get("why", ""),
                    message="Claim not supported by the other artifacts",
                ))
            for d in data.get("narrative_drift", []):
                findings.append(Finding(
                    rule="L2-semantic",
                    rule_name="semantic-narrative-drift",
                    severity="low",
                    source_a=", ".join(d.get("sources", [])),
                    source_b="",
                    quote_a=d.get("issue", ""),
                    quote_b="",
                    message="Narrative drift between artifacts",
                ))
    except Exception as exc:
        _semantic_unavailable(findings, f"{type(exc).__name__}: {exc}")


# ─── Report Generator & Public API ────────────────────────────────────────────

def format_report(result: CoherenceResult) -> str:
    """Format CoherenceResult into markdown table for COHERENCE.md."""
    lines = [
        "# Coherence Audit Report",
        "",
    ]
    if not result.findings:
        lines.extend([
            "No coherence issues found.",
            "",
            "**Verdict:** PASSED",
        ])
        return "\n".join(lines) + "\n"

    lines.extend([
        "| Rule | Severity | Source A | Source B | Description / Evidence |",
        "|---|---|---|---|---|",
    ])
    for f in result.findings:
        sev_upper = f.severity.upper()
        ev = f.message
        if f.quote_a or f.quote_b:
            ev += f" (A: `{f.quote_a[:40]}`, B: `{f.quote_b[:40]}`)"
        lines.append(f"| {f.rule} {f.rule_name} | {sev_upper} | {f.source_a} | {f.source_b} | {ev} |")

    high_count = sum(1 for f in result.findings if f.severity.lower() == "high")
    lines.append("")
    if high_count > 0:
        lines.append(f"**Verdict:** REJECTED ({high_count} HIGH severity issue(s) found)")
    else:
        lines.append("**Verdict:** PASSED (with warnings)")

    return "\n".join(lines) + "\n"


def check_dossier(
    application_dir: Path | str,
    semantic: bool = True,
    report_path: Path | str | None = None,
    write_report: bool = True,
) -> CoherenceResult:
    """
    Run Layer 1 deterministic coherence gate (R1..R8) and the Layer 2
    semantic review on an application folder.

    Writes COHERENCE.md report in application_dir (or report_path if specified)
    and updates .coherence.json when green (if write_report is True).
    """
    dir_path = Path(application_dir).resolve()
    artifacts = discover_artifacts(dir_path)
    result = CoherenceResult(application_dir=dir_path)

    # Discover enclosed supporting documents to extend evidence corpus
    _discover_enclosed_docs(artifacts, result.findings)

    # Run Layer 1 rules
    _check_r1_stale_artifact(artifacts, result.findings)
    _check_r2_diploma_support(artifacts, result.findings)
    _check_r3_diploma_contradiction(artifacts, result.findings)
    _check_r4_metric_support(artifacts, result.findings)
    _check_r5_identity(artifacts, result.findings)
    _check_r6_completeness(artifacts, result.findings)
    _check_r7_language(artifacts, result.findings)
    _check_r8_no_placeholder(artifacts, result.findings)

    # Layer 2 semantic pass (default on; no-ops when agy is unavailable)
    if semantic:
        _run_semantic_pass(artifacts, result.findings)

    # Write report if report_path explicitly specified or write_report is True
    report_md = format_report(result)

    if report_path:
        Path(report_path).write_text(report_md, encoding="utf-8")
    elif write_report:
        (dir_path / "COHERENCE.md").write_text(report_md, encoding="utf-8")

    # Update .coherence.json sidecar hashes when clean and write_report is True
    if result.passed and write_report:
        hashes: dict[str, str] = {}
        for path in [artifacts.cv_tex, artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt]:
            if path and path.exists():
                hashes[path.name] = _sha256_text(path)
        (dir_path / ".coherence.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    return result


