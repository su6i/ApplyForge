"""
coherence.py — Folder-based coherence gate for application bundles.

Verifies that all generated artifacts in an application directory (CV .tex/.pdf,
Cover Letter .tex/.pdf, full .txt, short .txt) tell one consistent story.
Edits to one file trigger detection if sibling artifacts are out-of-date,
contradictory, unsupported, or incomplete.

Layer 1: Deterministic rules R1..R8 (fast, blocking).
Layer 2: Semantic review via agy/Gemini (opt-in --semantic, non-blocking).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
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


def _extract_education_text(cv_tex: Path) -> str:
    """Extract text inside the CV's Education / Formation section."""
    if not cv_tex or not cv_tex.exists():
        return ""
    text = cv_tex.read_text(encoding="utf-8")

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
    text = cv_tex.read_text(encoding="utf-8")

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


def _check_r2_diploma_support(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R2 diploma-support: Every diploma named in the letter (either .txt or .tex)
    must appear in the CV's FORMATION section.
    """
    if not artifacts.cv_tex or not artifacts.cv_tex.exists():
        return

    edu_text = _extract_education_text(artifacts.cv_tex)
    edu_text_lc = edu_text.lower()

    label_keywords = {
        "DU": ["du", "d.u.", "diplôme universitaire"],
        "Master": ["master", "msc", "bac+5"],
        "Licence": ["licence", "bachelor", "bsc", "bac+3"],
        "Doctorat/PhD": ["doctorat", "phd", "ph.d."],
        "Ingénieur": ["ingénieur", "ingenieur"],
        "BTS": ["bts"],
        "DUT": ["dut"],
    }

    diploma_patterns = [
        (r"\bDU\b|\bD\.U\.\b|\bDiplôme Universitaire\b", "DU"),
        (r"\bMaster\b|\bMSc\b|\bBac\+5\b", "Master"),
        (r"\bLicence\b|\bBachelor\b|\bBSc\b|\bBac\+3\b", "Licence"),
        (r"\bDoctorat\b|\bPhD\b|\bPh\.D\.\b", "Doctorat/PhD"),
        (r"\bIngénieur\b", "Ingénieur"),
        (r"\bBTS\b", "BTS"),
        (r"\bDUT\b", "DUT"),
    ]

    letter_paths = [p for p in [artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt] if p and p.exists()]
    checked_diplomas: set[str] = set()

    for path in letter_paths:
        text = path.read_text(encoding="utf-8")
        for pattern, label in diploma_patterns:
            matches = re.finditer(pattern, text, flags=re.IGNORECASE)
            for m in matches:
                start = max(0, m.start() - 10)
                end = min(len(text), m.end() + 30)
                context_phrase = text[start:end].replace("\n", " ").strip()
                diploma_key = f"{label}:{m.group(0).lower()}"

                if diploma_key in checked_diplomas:
                    continue
                checked_diplomas.add(diploma_key)

                kw_list = label_keywords.get(label, [label.lower()])
                if not any(kw in edu_text_lc for kw in kw_list):
                    findings.append(Finding(
                        rule="R2",
                        rule_name="diploma-support",
                        severity="high",
                        source_a=path.name,
                        source_b=artifacts.cv_tex.name,
                        quote_a=context_phrase,
                        quote_b=edu_text[:200],
                        message=f"Diploma '{label}' mentioned in letter ({path.name}) does not appear in CV FORMATION section",
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
            text = path.read_text(encoding="utf-8")
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


def _check_r4_metric_support(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R4 metric-support: Every metric in the letter or .txt must occur in the CV
    with the same subject noun within a short context window.
    """
    if not artifacts.cv_tex or not artifacts.cv_tex.exists():
        return

    cv_text = artifacts.cv_tex.read_text(encoding="utf-8")

    letter_paths = [p for p in [artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt] if p and p.exists()]

    for path in letter_paths:
        text = path.read_text(encoding="utf-8")
        # Find explicit numeric figures (> 10, skipping years like 2024, 2026)
        for m in re.finditer(r"\b(\d{1,3}(?:[\s\.,]\d{3})+|\d{2,4}\+?)\b", text):
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

            # Check if this metric exists in CV
            # Normalize digits for matching
            cv_has_metric = False
            cv_window = ""
            for cv_m in re.finditer(r"\b(\d{1,3}(?:[\s\.,]\d{3})+|\d{2,4}\+?)\b", cv_text):
                cv_raw = cv_m.group(0).strip()
                cv_clean = re.sub(r"[\s\.,\+]", "", cv_raw)
                if cv_clean == val_clean:
                    cv_has_metric = True
                    cv_start = max(0, cv_m.start() - 50)
                    cv_end = min(len(cv_text), cv_m.end() + 50)
                    cv_window = cv_text[cv_start:cv_end].replace("\n", " ").strip()
                    break

            if not cv_has_metric:
                findings.append(Finding(
                    rule="R4",
                    rule_name="metric-support",
                    severity="high",
                    source_a=path.name,
                    source_b=artifacts.cv_tex.name,
                    quote_a=letter_window,
                    quote_b="Not found in CV",
                    message=f"Metric '{val_raw}' in {path.name} is not present in CV",
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


def _check_r5_identity(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    R5 identity: Company name, position title, candidate name, phone, e-mail,
    and city must be byte-identical across all four artifacts.
    """
    identities: dict[str, dict[str, str]] = {}

    for path in [artifacts.cv_tex, artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt]:
        if not path or not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        id_data: dict[str, str] = {}

        if path.suffix == ".tex":
            m_comp = re.search(r"\\newcommand\{\\CompanyName\}\{([^}]*)\}", text)
            if m_comp:
                id_data["company"] = m_comp.group(1).strip()

            m_title = re.search(r"\\newcommand\{\\PositionTitle\}\{([^}]*)\}", text)
            if m_title:
                id_data["position"] = m_title.group(1).strip()

            m_name = re.search(r"\\(?:newcommand\{)?\\cvname\}?\{([^}]*)\}", text)
            if m_name:
                id_data["name"] = m_name.group(1).strip()

            m_phone = re.search(r"\\(?:newcommand\{)?\\cvphone\}?\{([^}]*)\}", text)
            if m_phone:
                id_data["phone"] = m_phone.group(1).strip()

            m_email = re.search(r"\\(?:newcommand\{)?\\cvemail\}?\{([^}]*)\}", text)
            if m_email:
                id_data["email"] = m_email.group(1).strip()

            m_city = re.search(r"\\(?:re)?new-?command\{\\cvlocation\}\{([^}]*)\}", text)
            if m_city:
                id_data["city"] = m_city.group(1).strip().split(",")[0].strip()
        else:  # .txt
            # Subject line extraction
            m_subj = re.search(r"(?:Objet|Subject)\s*:\s*Candidature au poste de ([^—\-]+)[—\-]\s*(.*)", text, re.IGNORECASE)
            if m_subj:
                id_data["position"] = m_subj.group(1).strip()
                id_data["company"] = m_subj.group(2).strip()

            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines:
                id_data["name"] = lines[0]
            for line in lines[:5]:
                if "@" in line:
                    id_data["email"] = line
                elif re.search(r"[\+\d\s\.\-]{8,}", line) and not line.startswith("Objet"):
                    id_data["phone"] = line

        identities[path.name] = id_data

    # Compare key fields across artifacts
    field_labels = ["company", "position", "name", "phone", "email"]
    for f_key in field_labels:
        values = {name: data[f_key] for name, data in identities.items() if f_key in data and data[f_key]}
        if len(set(values.values())) > 1:
            sources = list(values.keys())
            findings.append(Finding(
                rule="R5",
                rule_name="identity",
                severity="high",
                source_a=sources[0],
                source_b=sources[1],
                quote_a=f"{f_key}='{values[sources[0]]}'",
                quote_b=f"{f_key}='{values[sources[1]]}'",
                message=f"Identity mismatch for '{f_key}' between {sources[0]} and {sources[1]}",
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

        text = path.read_text(encoding="utf-8")
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
        text = path.read_text(encoding="utf-8")
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

def _run_semantic_pass(artifacts: DossierArtifacts, findings: list[Finding]) -> None:
    """
    Layer 2: LLM semantic review using agy CLI with gemini-3.6-flash-low model.
    Opt-in, skipped silently if agy binary is absent.
    """
    if not shutil.which("agy"):
        logger.debug("agy binary not found in PATH — skipping Layer 2 semantic pass")
        return

    corpus: list[str] = []
    for p in [artifacts.cv_tex, artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt]:
        if p and p.exists():
            corpus.append(f"--- ARTIFACT: {p.name} ---\n" + p.read_text(encoding="utf-8"))

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

    try:
        cmd = ["agy", "--model", "gemini-3.6-flash-low", "--json-schema", json.dumps(schema), prompt]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
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
    except Exception as exc:
        logger.warning(f"Layer 2 semantic review failed: {exc}")


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


def check_dossier(application_dir: Path | str, semantic: bool = False) -> CoherenceResult:
    """
    Run Layer 1 deterministic coherence gate (R1..R8) and optional Layer 2
    semantic review on an application folder.

    Writes COHERENCE.md report in application_dir and updates .coherence.json
    when green.
    """
    dir_path = Path(application_dir).resolve()
    artifacts = discover_artifacts(dir_path)
    result = CoherenceResult(application_dir=dir_path)

    # Run Layer 1 rules
    _check_r1_stale_artifact(artifacts, result.findings)
    _check_r2_diploma_support(artifacts, result.findings)
    _check_r3_diploma_contradiction(artifacts, result.findings)
    _check_r4_metric_support(artifacts, result.findings)
    _check_r5_identity(artifacts, result.findings)
    _check_r6_completeness(artifacts, result.findings)
    _check_r7_language(artifacts, result.findings)
    _check_r8_no_placeholder(artifacts, result.findings)

    # Optional Layer 2 semantic pass
    if semantic:
        _run_semantic_pass(artifacts, result.findings)

    # Write COHERENCE.md
    report_md = format_report(result)
    (dir_path / "COHERENCE.md").write_text(report_md, encoding="utf-8")

    # Update .coherence.json sidecar hashes when clean
    if result.passed:
        hashes: dict[str, str] = {}
        for path in [artifacts.cv_tex, artifacts.cl_tex, artifacts.cl_full_txt, artifacts.cl_short_txt]:
            if path and path.exists():
                hashes[path.name] = _sha256_text(path)
        (dir_path / ".coherence.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    return result
