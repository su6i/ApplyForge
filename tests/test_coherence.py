"""
test_coherence.py — Acceptance and unit tests for the coherence gate (R1..R8).

Tests include:
  - Clean dossier: returns zero findings and passed == True.
  - Defect D1 & D2: stale artifacts (R1 fires).
  - Defect D3: missing diploma in CV FORMATION section (R2 fires).
  - Defect D4: unsupported / context-mismatched metric in letter (R4 fires).
  - Individual tests verifying each rule R1..R8 fires as expected.
"""

import time
from pathlib import Path

import pytest

from src.pipeline import coherence as coherence_mod
from src.pipeline.coherence import check_dossier


@pytest.fixture(autouse=True)
def _no_semantic_pass(monkeypatch):
    """Layer 2 is on by default in production; keep the suite offline and
    deterministic by stubbing it out for every test in this module."""
    monkeypatch.setattr(coherence_mod, "_run_semantic_pass", lambda *a, **k: None)


def _create_clean_dossier(tmp_path: Path) -> Path:
    """Helper creating a fully consistent 6-artifact application folder."""
    app_dir = tmp_path / "2026-08-03_Acme_Support_fr"
    app_dir.mkdir(parents=True, exist_ok=True)

    cv_tex = r"""
\documentclass{article}
\newcommand{\cvname}{Alex Smith}
\newcommand{\cvemail}{alex@example.com}
\newcommand{\cvphone}{+00-00000000}
\newcommand{\cvlocation}{Montpellier}
\newcommand{\CompanyName}{Acme Corp}
\newcommand{\PositionTitle}{Technicien Support}

\begin{document}
\cvsection{Profile}
Ingénieur Support Réseau avec expérience en automatisation et diplôme DU Big Data.

\cvsection{Experience}
Support N2/N3 pour 1 500 utilisateurs sur infrastructure Cisco.

\cvsection{Formation}
\cvevent{Master en Informatique}{Université de Montpellier}{2022-2024}{}
\cvevent{DU Big Data, Data Science}{Université de Montpellier}{2021-2022}{}
\cvevent{Licence Informatique}{Université de Montpellier}{2019-2021}{}
\end{document}
"""
    cl_tex = r"""
\documentclass{article}
\newcommand{\CompanyName}{Acme Corp}
\newcommand{\PositionTitle}{Technicien Support}
\newcommand{\cvname}{Alex Smith}
\newcommand{\cvemail}{alex@example.com}
\newcommand{\cvphone}{+00-00000000}
\newcommand{\cvlocation}{Montpellier}

\begin{document}
Madame, Monsieur,

Titulaire du Master en Informatique et du DU Big Data, je souhaite candidater chez Acme Corp.
J'ai assuré le support N2/N3 pour 1 500 utilisateurs.

Dans l'attente de votre retour, je vous prie d'agréer mes salutations distinguées.
Alex Smith
\end{document}
"""
    cl_full = """Alex Smith
Montpellier
+00-00000000
alex@example.com

Objet : Candidature au poste de Technicien Support — Acme Corp

Madame, Monsieur,

Titulaire du Master en Informatique et du DU Big Data, je souhaite candidater chez Acme Corp.
J'ai assuré le support N2/N3 pour 1 500 utilisateurs.

Dans l'attente de votre retour, je vous prie d'agréer mes salutations distinguées.

Alex Smith
"""
    cl_short = """Alex Smith
Montpellier
+00-00000000
alex@example.com

Objet : Candidature au poste de Technicien Support — Acme Corp

Madame, Monsieur,

Titulaire du Master et du DU Big Data, je canddate pour le poste de Technicien Support chez Acme Corp.
Support pour 1 500 utilisateurs.

Cordialement,
Alex Smith
"""

    (app_dir / "cv-owner-CV_Support_fr.tex").write_text(cv_tex, encoding="utf-8")
    (app_dir / "cv-owner-LettreMotivation_Support_fr.tex").write_text(
        cl_tex, encoding="utf-8"
    )
    (app_dir / "cv-owner-LettreMotivation_Support_fr.txt").write_text(
        cl_full, encoding="utf-8"
    )
    (app_dir / "cv-owner-LettreMotivation_Courte_Support_fr.txt").write_text(
        cl_short, encoding="utf-8"
    )

    # Touch PDFs after TEX so mtimes are clean
    time.sleep(0.02)
    (app_dir / "cv-owner-CV_Support_fr.pdf").write_bytes(b"%PDF-1.4 dummy")
    (app_dir / "cv-owner-LettreMotivation_Support_fr.pdf").write_bytes(
        b"%PDF-1.4 dummy"
    )

    return app_dir


# ─── Acceptance Tests ─────────────────────────────────────────────────────────


def test_clean_dossier_passes(tmp_path: Path) -> None:
    """Clean application folder yields zero findings and passes."""
    dossier = _create_clean_dossier(tmp_path)
    result = check_dossier(dossier)
    assert result.passed
    assert len(result.findings) == 0
    assert (dossier / "COHERENCE.md").exists()
    assert (dossier / ".coherence.json").exists()


def test_d1_d2_stale_artifact(tmp_path: Path) -> None:
    """
    Defects D1 & D2: CV .tex modified at 03:00, letter .tex at 01:32, .txt at 01:31.
    Asserts R1 stale-artifact fires.
    """
    dossier = _create_clean_dossier(tmp_path)

    # Make letter .tex and .txt older than CV .tex
    cl_tex = dossier / "cv-owner-LettreMotivation_Support_fr.tex"
    cl_txt = dossier / "cv-owner-LettreMotivation_Support_fr.txt"

    past_time = time.time() - 3600
    import os

    os.utime(cl_tex, (past_time, past_time))
    os.utime(cl_txt, (past_time - 60, past_time - 60))

    result = check_dossier(dossier)
    assert not result.passed
    r1_findings = [f for f in result.findings if f.rule == "R1"]
    assert len(r1_findings) > 0
    assert any("older than" in f.message for f in r1_findings)


def test_d3_diploma_support(tmp_path: Path) -> None:
    """
    Defect D3: Letter argues from DU Big Data, but CV FORMATION listed only Master + Licence.
    Asserts R2 diploma-support fires.
    """
    dossier = _create_clean_dossier(tmp_path)
    cv_tex_path = dossier / "cv-owner-CV_Support_fr.tex"

    # Remove DU Big Data from CV FORMATION section
    cv_tex = cv_tex_path.read_text(encoding="utf-8")
    cv_tex_no_du = cv_tex.replace(
        r"\cvevent{DU Big Data, Data Science}{Université de Montpellier}{2021-2022}{}",
        "",
    )
    cv_tex_path.write_text(cv_tex_no_du, encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    r2_findings = [f for f in result.findings if f.rule == "R2"]
    assert len(r2_findings) > 0
    assert any("DU" in f.message for f in r2_findings)


def test_d4_metric_support(tmp_path: Path) -> None:
    """
    Defect D4: Short .txt claims "tableaux de bord Power BI utilisés par 1 500+ utilisateurs",
    whereas CV attributes 1 500 users to N2/N3 support and never mentions Power BI.
    Asserts R4 metric-support fires.
    """
    dossier = _create_clean_dossier(tmp_path)
    short_txt_path = dossier / "cv-owner-LettreMotivation_Courte_Support_fr.txt"

    # Mutate short text to add mismatched Power BI claim for 1 500 users
    text = short_txt_path.read_text(encoding="utf-8")
    text_bad = text.replace(
        "Support pour 1 500 utilisateurs.",
        "J'ai déployé des tableaux de bord Power BI utilisés par 1 500+ utilisateurs.",
    )
    short_txt_path.write_text(text_bad, encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    r4_findings = [f for f in result.findings if f.rule == "R4"]
    assert len(r4_findings) > 0
    assert any("Power BI" in f.message or "attached" in f.message for f in r4_findings)


# ─── Individual Rule Unit Tests (R1 .. R8) ───────────────────────────────────


def test_rule_r1_stale_artifact(tmp_path: Path) -> None:
    """R1 fires when PDF is older than TEX."""
    dossier = _create_clean_dossier(tmp_path)
    pdf = dossier / "cv-owner-CV_Support_fr.pdf"
    import os

    os.utime(pdf, (1000, 1000))

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R1" for f in result.findings)


def test_rule_r2_diploma_support(tmp_path: Path) -> None:
    """R2 fires when diploma in letter is missing from CV FORMATION."""
    dossier = _create_clean_dossier(tmp_path)
    cl_tex = dossier / "cv-owner-LettreMotivation_Support_fr.tex"
    cl_tex.write_text(
        cl_tex.read_text(encoding="utf-8").replace("DU Big Data", "Doctorat en IA"),
        encoding="utf-8",
    )

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R2" and "Doctorat" in f.message for f in result.findings)


def test_rule_r3_diploma_contradiction(tmp_path: Path) -> None:
    """R3 fires when letter degree framing contradicts CV profile framing."""
    dossier = _create_clean_dossier(tmp_path)
    # CV profile emphasizes DU Big Data without Master; letter frames primary degree as Master without DU
    cv_tex = dossier / "cv-owner-CV_Support_fr.tex"
    cv_tex.write_text(
        cv_tex.read_text(encoding="utf-8").replace("Master en Informatique", "DUT"),
        encoding="utf-8",
    )

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R3" or f.rule == "R2" for f in result.findings)


def test_rule_r4_metric_support(tmp_path: Path) -> None:
    """R4 fires when metric in letter is completely missing from CV."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt.write_text(
        cl_txt.read_text(encoding="utf-8") + "\nGéré 922 000 requêtes API.",
        encoding="utf-8",
    )

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R4" and "922" in f.message for f in result.findings)


def test_rule_r5_identity(tmp_path: Path) -> None:
    """R5 fires when company name differs between CV .tex and Letter .tex."""
    dossier = _create_clean_dossier(tmp_path)
    cl_tex = dossier / "cv-owner-LettreMotivation_Support_fr.tex"
    cl_tex.write_text(
        cl_tex.read_text(encoding="utf-8").replace(
            r"\newcommand{\CompanyName}{Acme Corp}",
            r"\newcommand{\CompanyName}{Other Corp}",
        ),
        encoding="utf-8",
    )

    result = check_dossier(dossier)
    assert not result.passed
    assert any(
        f.rule == "R5" and "CompanyName" in f.message or "company" in f.message
        for f in result.findings
    )


def test_rule_r6_completeness(tmp_path: Path) -> None:
    """R6 fires when short .txt exceeds 1500 characters or artifact missing."""
    dossier = _create_clean_dossier(tmp_path)
    short_txt = dossier / "cv-owner-LettreMotivation_Courte_Support_fr.txt"
    short_txt.write_text("Long text... " * 200, encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R6" and "1500" in f.message for f in result.findings)


def test_rule_r7_language(tmp_path: Path) -> None:
    """R7 fires when Persian characters are inserted into a French artifact."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt.write_text(
        cl_txt.read_text(encoding="utf-8") + "\nسلام دنیا", encoding="utf-8"
    )

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R7" and "Persian" in f.message for f in result.findings)


def test_rule_r8_no_placeholder(tmp_path: Path) -> None:
    """R8 fires when unfilled placeholder like [Company Name] or [...] is found."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt.write_text(
        cl_txt.read_text(encoding="utf-8").replace("Acme Corp", "[Company Name]"),
        encoding="utf-8",
    )

    result = check_dossier(dossier)
    assert not result.passed
    assert any(
        f.rule == "R8" and "[Company Name]" in f.quote_a for f in result.findings
    )


def test_r2_diplome_d_universite_support(tmp_path: Path) -> None:
    """
    R2 fires when letter names 'Diplôme d'Université' but CV FORMATION contains only Licence
    at an institution with preposition 'du' (e.g. Institut Jahade Daneshgahi du Khouzestan).
    """
    dossier = _create_clean_dossier(tmp_path)
    cv_tex_path = dossier / "cv-owner-CV_Support_fr.tex"
    cl_tex_path = dossier / "cv-owner-LettreMotivation_Support_fr.tex"
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_short_path = dossier / "cv-owner-LettreMotivation_Courte_Support_fr.txt"

    # CV FORMATION section has Licence at "Institut Jahade Daneshgahi du Khouzestan" but NO DU
    cv_tex = cv_tex_path.read_text(encoding="utf-8")
    cv_tex_no_du = cv_tex.replace(
        r"\cvevent{DU Big Data, Data Science}{Université de Montpellier}{2021-2022}{}",
        r"\cvevent{Licence}{Institut Jahade Daneshgahi du Khouzestan}{2019-2021}{}",
    )
    cv_tex_path.write_text(cv_tex_no_du, encoding="utf-8")

    # Letter names "Diplôme d'Université"
    cl_tex = cl_tex_path.read_text(encoding="utf-8").replace(
        "du DU Big Data", "du Diplôme d'Université en Big Data"
    )
    cl_tex_path.write_text(cl_tex, encoding="utf-8")
    cl_txt = cl_txt_path.read_text(encoding="utf-8").replace(
        "du DU Big Data", "du Diplôme d'Université en Big Data"
    )
    cl_txt_path.write_text(cl_txt, encoding="utf-8")
    cl_short = cl_short_path.read_text(encoding="utf-8").replace(
        "du DU Big Data", "du Diplôme d'Université en Big Data"
    )
    cl_short_path.write_text(cl_short, encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    r2_findings = [f for f in result.findings if f.rule == "R2"]
    assert len(r2_findings) > 0
    assert any("DU" in f.message for f in r2_findings)


def test_r8_ignores_placeholder_in_latex_comment(tmp_path: Path) -> None:
    """R8 passes when [...] placeholder is contained entirely within a LaTeX %-comment line."""
    dossier = _create_clean_dossier(tmp_path)
    cl_tex_path = dossier / "cv-owner-LettreMotivation_Support_fr.tex"

    # Insert comment line containing [...] into letter .tex
    cl_tex = cl_tex_path.read_text(encoding="utf-8")
    cl_tex_with_comment = (
        "% ⚠️ DO NOT leave any placeholder brackets [...] in the final version.\n"
        + cl_tex
    )
    cl_tex_path.write_text(cl_tex_with_comment, encoding="utf-8")

    result = check_dossier(dossier)
    r8_findings = [f for f in result.findings if f.rule == "R8"]
    assert len(r8_findings) == 0


def test_r5_position_title_with_dash(tmp_path: Path) -> None:
    """R5 does not report false positive position/company mismatch when position title contains a dash."""
    dossier = _create_clean_dossier(tmp_path)
    cv_tex_path = dossier / "cv-owner-CV_Support_fr.tex"
    cl_tex_path = dossier / "cv-owner-LettreMotivation_Support_fr.tex"
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_short_path = dossier / "cv-owner-LettreMotivation_Courte_Support_fr.txt"

    pos_title = "Reconversion Consultant(e) SAP - Roanne"
    company = "Sopra Steria"

    # Update CV .tex
    cv_tex = cv_tex_path.read_text(encoding="utf-8")
    cv_tex = cv_tex.replace(
        r"\newcommand{\PositionTitle}{Technicien Support}",
        f"\\newcommand{{\\PositionTitle}}{{{pos_title}}}",
    )
    cv_tex = cv_tex.replace(
        r"\newcommand{\CompanyName}{Acme Corp}",
        f"\\newcommand{{\\CompanyName}}{{{company}}}",
    )
    cv_tex_path.write_text(cv_tex, encoding="utf-8")

    # Update Letter .tex
    cl_tex = cl_tex_path.read_text(encoding="utf-8")
    cl_tex = cl_tex.replace(
        r"\newcommand{\PositionTitle}{Technicien Support}",
        f"\\newcommand{{\\PositionTitle}}{{{pos_title}}}",
    )
    cl_tex = cl_tex.replace(
        r"\newcommand{\CompanyName}{Acme Corp}",
        f"\\newcommand{{\\CompanyName}}{{{company}}}",
    )
    cl_tex_path.write_text(cl_tex, encoding="utf-8")

    # Update .txt full
    cl_txt = cl_txt_path.read_text(encoding="utf-8")
    cl_txt = cl_txt.replace(
        "Objet : Candidature au poste de Technicien Support — Acme Corp",
        f"Objet : Candidature au poste de {pos_title} — {company}",
    )
    cl_txt_path.write_text(cl_txt, encoding="utf-8")

    # Update .txt short
    cl_short = cl_short_path.read_text(encoding="utf-8")
    cl_short = cl_short.replace(
        "Objet : Candidature au poste de Technicien Support — Acme Corp",
        f"Objet : Candidature au poste de {pos_title}",
    )
    cl_short_path.write_text(cl_short, encoding="utf-8")

    result = check_dossier(dossier)
    r5_findings = [f for f in result.findings if f.rule == "R5"]
    assert len(r5_findings) == 0, f"Unexpected R5 findings: {r5_findings}"


def test_r5_short_letter_signature_name_only(tmp_path: Path) -> None:
    """R5 extracts candidate name from signature block when short letter has no contact header."""
    dossier = _create_clean_dossier(tmp_path)
    cl_short_path = dossier / "cv-owner-LettreMotivation_Courte_Support_fr.txt"

    # Rewrite short letter without top header lines (starts directly with Objet line)
    short_content = """Objet : Candidature au poste de Technicien Support — Acme Corp

Madame, Monsieur,

Titulaire du Master et du DU Big Data, je candidate pour le poste de Technicien Support chez Acme Corp.
Support pour 1 500 utilisateurs.

Cordialement,
Alex Smith
+00-00000000 — alex@example.com
"""
    cl_short_path.write_text(short_content, encoding="utf-8")

    result = check_dossier(dossier)
    r5_findings = [f for f in result.findings if f.rule == "R5"]
    assert len(r5_findings) == 0, f"Unexpected R5 findings: {r5_findings}"


def test_r5_subject_parsing_separators() -> None:
    """Unit tests for _parse_subject_line handling of dashes and English/French templates."""
    from src.pipeline.coherence import _parse_subject_line

    pos, comp = _parse_subject_line(
        "Objet : Candidature au poste de Reconversion Consultant(e) SAP - Roanne — Sopra Steria"
    )
    assert pos == "Reconversion Consultant(e) SAP - Roanne"
    assert comp == "Sopra Steria"

    pos, comp = _parse_subject_line(
        "Objet : Candidature au poste de Reconversion Consultant(e) SAP - Roanne"
    )
    assert pos == "Reconversion Consultant(e) SAP - Roanne"
    assert comp is None

    pos, comp = _parse_subject_line(
        "Subject: Application for the Senior DevOps Engineer position — ACME Corp"
    )
    assert pos == "Senior DevOps Engineer"
    assert comp == "ACME Corp"


# ─── T-024 False Positive & True Positive Regression Tests ────────────────────


def test_r4_phone_and_orcid_not_flagged_as_metrics(tmp_path: Path) -> None:
    """Fix 1 (FP): Phone numbers (+33 6 00 00 00 00, 06.00.00.00.00) and ORCIDs (0000-0002-1825-0097) are not flagged as metrics."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt = cl_txt_path.read_text(encoding="utf-8")
    cl_txt += (
        "\nPhone: +33 6 00 00 00 00 / 06.00.00.00.00\nORCID: 0000-0002-1825-0097\n"
    )
    cl_txt_path.write_text(cl_txt, encoding="utf-8")

    result = check_dossier(dossier)
    r4_findings = [f for f in result.findings if f.rule == "R4"]
    assert len(r4_findings) == 0, (
        f"Unexpected R4 findings for phone/ORCID: {r4_findings}"
    )


def test_r4_unsupported_numeric_claim_still_flagged(tmp_path: Path) -> None:
    """Fix 1 (TP): An unsupported numeric claim (e.g. 45 000) in letter is still flagged by R4."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt = cl_txt_path.read_text(encoding="utf-8")
    cl_txt += "\nJ'ai géré un budget de 45 000 € en autonomie.\n"
    cl_txt_path.write_text(cl_txt, encoding="utf-8")

    result = check_dossier(dossier)
    r4_findings = [f for f in result.findings if f.rule == "R4"]
    assert len(r4_findings) > 0
    assert any("45" in f.message for f in r4_findings)


def test_r4_latex_number_formatting_not_flagged(tmp_path: Path) -> None:
    r"""Fix 2 (FP): LaTeX number decorations ({,}, \, ~, \%) match normalized numbers in CV."""
    dossier = _create_clean_dossier(tmp_path)
    cl_tex_path = dossier / "cv-owner-LettreMotivation_Support_fr.tex"
    cl_full_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_short_path = dossier / "cv-owner-LettreMotivation_Courte_Support_fr.txt"
    cv_tex_path = dossier / "cv-owner-CV_Support_fr.tex"

    cl_tex_path.write_text(
        cl_tex_path.read_text("utf-8").replace(
            "1 500 utilisateurs", r"18{,}000 utilisateurs et 18\,000 requêtes"
        ),
        "utf-8",
    )
    cl_full_path.write_text(
        cl_full_path.read_text("utf-8").replace("1 500", "18 000"), "utf-8"
    )
    cl_short_path.write_text(
        cl_short_path.read_text("utf-8").replace("1 500", "18 000"), "utf-8"
    )
    cv_tex_path.write_text(
        cv_tex_path.read_text("utf-8").replace(
            "1 500 utilisateurs", "18 000 utilisateurs et 18 000 requêtes"
        ),
        "utf-8",
    )

    result = check_dossier(dossier)
    r4_findings = [f for f in result.findings if f.rule == "R4"]
    assert len(r4_findings) == 0, (
        f"Unexpected R4 findings for LaTeX formatted numbers: {r4_findings}"
    )


def test_r4_mismatched_latex_number_still_flagged(tmp_path: Path) -> None:
    """Fix 2 (TP): Mismatched LaTeX number (e.g. 18{,}000 attached to Power BI) is still flagged by R4."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt = cl_txt_path.read_text(encoding="utf-8")
    cl_txt += "\nTableaux de bord Power BI pour 18{,}000 utilisateurs.\n"
    cl_txt_path.write_text(cl_txt, encoding="utf-8")

    result = check_dossier(dossier)
    r4_findings = [f for f in result.findings if f.rule == "R4"]
    assert len(r4_findings) > 0
    assert any("18" in f.message for f in r4_findings)


def test_r2_applied_for_phd_position_not_flagged(tmp_path: Path) -> None:
    """Fix 3 (FP): Applied-for PhD position ('candidature au poste de doctorat') is not flagged by R2 as missing degree."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt = """Alex Smith
Montpellier

Objet : Candidature au poste de doctorat en informatique — LITIS

Madame, Monsieur,

I am applying for the PhD position at LITIS. Je souhaite candidater au poste de doctorat.

Cordialement,
Alex Smith
"""
    cl_txt_path.write_text(cl_txt, encoding="utf-8")

    result = check_dossier(dossier)
    r2_findings = [f for f in result.findings if f.rule == "R2"]
    assert len(r2_findings) == 0, (
        f"Unexpected R2 findings for applied PhD position: {r2_findings}"
    )


def test_r2_unsupported_claimed_phd_still_flagged(tmp_path: Path) -> None:
    """Fix 3 (TP): Claimed PhD degree ('Titulaire d'un Doctorat') missing from CV FORMATION is still flagged by R2."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt = cl_txt_path.read_text(encoding="utf-8")
    cl_txt = cl_txt.replace("Titulaire du Master", "Titulaire d'un Doctorat")
    cl_txt_path.write_text(cl_txt, encoding="utf-8")

    result = check_dossier(dossier)
    r2_findings = [f for f in result.findings if f.rule == "R2"]
    assert len(r2_findings) > 0
    assert any("Doctorat" in f.message for f in r2_findings)


def test_r2_r4_enclosed_supporting_documents_support_claims(tmp_path: Path) -> None:
    """Fix 4 (FP): Claims (diploma DU Big Data, metric 50 000 €) backed by enclosed context file are not reported unsupported."""
    dossier = _create_clean_dossier(tmp_path)
    cv_tex_path = dossier / "cv-owner-CV_Support_fr.tex"
    cl_tex_path = dossier / "cv-owner-LettreMotivation_Support_fr.tex"
    cl_full_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_short_path = dossier / "cv-owner-LettreMotivation_Courte_Support_fr.txt"

    # Remove DU Big Data and 1 500 metric from CV
    cv_tex = cv_tex_path.read_text(encoding="utf-8")
    cv_tex = cv_tex.replace(
        r"\cvevent{DU Big Data, Data Science}{Université de Montpellier}{2021-2022}{}",
        "",
    )
    cv_tex = cv_tex.replace("1 500", "50")
    cv_tex_path.write_text(cv_tex, encoding="utf-8")

    # Add enclosed supporting document under context/
    ctx_dir = dossier / "context"
    ctx_dir.mkdir(exist_ok=True)
    rec_letter = ctx_dir / "recommendation.txt"
    rec_letter.write_text(
        "M. Smith est titulaire du DU Big Data et a géré un budget de 50 000 €.",
        encoding="utf-8",
    )

    # Letter files assert DU Big Data and 50 000 €
    cl_tex_path.write_text(
        cl_tex_path.read_text("utf-8").replace("1 500", "50 000"), "utf-8"
    )
    cl_full_path.write_text(
        cl_full_path.read_text("utf-8").replace("1 500", "50 000"), "utf-8"
    )
    cl_short_path.write_text(
        cl_short_path.read_text("utf-8").replace("1 500", "50 000"), "utf-8"
    )

    result = check_dossier(dossier)
    r2_findings = [f for f in result.findings if f.rule == "R2"]
    r4_findings = [f for f in result.findings if f.rule == "R4"]
    assert len(r2_findings) == 0, f"Unexpected R2 findings: {r2_findings}"
    assert len(r4_findings) == 0, f"Unexpected R4 findings: {r4_findings}"


def test_r2_r4_unsupported_claims_not_in_enclosed_docs_still_flagged(
    tmp_path: Path,
) -> None:
    """Fix 4 (TP): Claims absent from both CV and enclosed documents are still flagged."""
    dossier = _create_clean_dossier(tmp_path)
    ctx_dir = dossier / "context"
    ctx_dir.mkdir(exist_ok=True)
    (ctx_dir / "letter.txt").write_text(
        "Context document without relevant claims.", encoding="utf-8"
    )

    # Remove DU Big Data from CV
    cv_tex_path = dossier / "cv-owner-CV_Support_fr.tex"
    cv_tex = cv_tex_path.read_text(encoding="utf-8")
    cv_tex = cv_tex.replace(
        r"\cvevent{DU Big Data, Data Science}{Université de Montpellier}{2021-2022}{}",
        "",
    )
    cv_tex_path.write_text(cv_tex, encoding="utf-8")

    # Add unsupported metric 99 000 to letter
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt = cl_txt_path.read_text(encoding="utf-8") + "\nGéré 99 000 requêtes."
    cl_txt_path.write_text(cl_txt, encoding="utf-8")

    result = check_dossier(dossier)
    r2_findings = [f for f in result.findings if f.rule == "R2"]
    r4_findings = [f for f in result.findings if f.rule == "R4"]
    assert len(r2_findings) > 0
    assert len(r4_findings) > 0


def test_enclosed_unextractable_pdf_emits_info_finding(tmp_path: Path) -> None:
    """Fix 4 (unextractable PDF): A corrupted enclosed PDF emits an INFO-level finding and does not fail the gate."""
    dossier = _create_clean_dossier(tmp_path)
    ctx_dir = dossier / "context"
    ctx_dir.mkdir(exist_ok=True)
    (ctx_dir / "scanned_corrupted.pdf").write_bytes(
        b"%PDF-1.4 INVALID CORRUPTED CONTENT"
    )

    result = check_dossier(dossier)
    info_findings = [f for f in result.findings if f.severity == "info"]
    assert len(info_findings) > 0
    assert any("scanned_corrupted.pdf" in f.source_a for f in info_findings)
    assert result.passed


# ─── FP-5, FP-6, FP-7 Tests (Task T-024 Round 2) ──────────────────────────────


def test_fp5_bounded_and_approximate_metrics_supported(tmp_path: Path) -> None:
    """FP-5: 'over 18,000', '~500', and '100+' in cover letter supported by source values satisfying bound."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_short_path = dossier / "cv-owner-LettreMotivation_Courte_Support_fr.txt"
    cl_tex_path = dossier / "cv-owner-LettreMotivation_Support_fr.tex"
    cv_tex_path = dossier / "cv-owner-CV_Support_fr.tex"

    # CV has exact figures: 18,169 clauses, 520 documents, 120 requests
    cv_tex = cv_tex_path.read_text(encoding="utf-8")
    cv_tex = cv_tex.replace("1 500", "18,169 clauses, 520 documents, 120 requests")
    cv_tex_path.write_text(cv_tex, encoding="utf-8")

    # Letter uses bounded/approximate phrasing: over 18,000, ~500, 100+
    for p in [cl_txt_path, cl_short_path, cl_tex_path]:
        content = p.read_text(encoding="utf-8")
        content = content.replace(
            "1 500", "over 18,000 clauses, ~500 documents, 100+ requests"
        )
        p.write_text(content, encoding="utf-8")

    result = check_dossier(dossier)
    r4_findings = [f for f in result.findings if f.rule == "R4"]
    assert len(r4_findings) == 0, f"Unexpected R4 findings: {r4_findings}"


def test_fp5_unsupported_bounded_metric_still_flagged(tmp_path: Path) -> None:
    """FP-5 TP: 'over 18,000' when CV has only 900, or exact '18,000' when CV has 18,169 is STILL flagged."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt_path = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cv_tex_path = dossier / "cv-owner-CV_Support_fr.tex"

    # CV has 900
    cv_tex = cv_tex_path.read_text(encoding="utf-8")
    cv_tex = cv_tex.replace("1 500", "900 clauses")
    cv_tex_path.write_text(cv_tex, encoding="utf-8")

    # Letter claims over 18,000 and exact 18,000
    cl_txt = (
        cl_txt_path.read_text(encoding="utf-8")
        + "\nTraité over 18,000 clauses and exact 18,000 clauses."
    )
    cl_txt_path.write_text(cl_txt, encoding="utf-8")

    result = check_dossier(dossier)
    r4_findings = [f for f in result.findings if f.rule == "R4"]
    assert len(r4_findings) > 0
    assert any("18,000" in f.message for f in r4_findings)


def test_fp6_academic_dossier_requires_email_draft_not_txt_letters(
    tmp_path: Path,
) -> None:
    """FP-6: An academic PhD dossier requiring email_draft.md passes without .txt letters."""
    dossier = tmp_path / "PhD_Dossier"
    dossier.mkdir()

    (dossier / "Amir_CV_PhD_en.tex").write_text(
        r"\documentclass{article}\begin{document}PhD CV\end{document}", encoding="utf-8"
    )
    (dossier / "Amir_CV_PhD_en.pdf").write_bytes(b"%PDF-1.4 mock pdf")
    (dossier / "Amir_CoverLetter_PhD_en.tex").write_text(
        r"\documentclass{article}\begin{document}PhD Cover Letter\end{document}",
        encoding="utf-8",
    )
    (dossier / "Amir_CoverLetter_PhD_en.pdf").write_bytes(b"%PDF-1.4 mock pdf")
    (dossier / "email_draft.md").write_text(
        "Subject: PhD Application\n\nDear Prof...", encoding="utf-8"
    )

    result = check_dossier(dossier, semantic=False)
    r6_findings = [f for f in result.findings if f.rule == "R6"]
    assert len(r6_findings) == 0, f"Unexpected R6 findings: {r6_findings}"
    assert result.passed


def test_fp6_job_dossier_missing_txt_letters_still_flagged(tmp_path: Path) -> None:
    """FP-6 TP: Job dossier missing .txt letters is flagged; academic dossier missing email_draft is flagged."""
    # 1. Job dossier missing .txt letters
    job_dir = tmp_path / "Job_Dossier"
    job_dir.mkdir()
    (job_dir / "JobPosting.md").write_text("Job posting content", encoding="utf-8")
    (job_dir / "CV_en.tex").write_text(
        r"\documentclass{article}\begin{document}CV\end{document}", encoding="utf-8"
    )
    (job_dir / "CV_en.pdf").write_bytes(b"%PDF-1.4 mock pdf")
    (job_dir / "CoverLetter_en.tex").write_text(
        r"\documentclass{article}\begin{document}Letter\end{document}", encoding="utf-8"
    )
    (job_dir / "CoverLetter_en.pdf").write_bytes(b"%PDF-1.4 mock pdf")

    res_job = check_dossier(job_dir, semantic=False)
    r6_job = [f for f in res_job.findings if f.rule == "R6"]
    assert len(r6_job) >= 2
    assert any("Full cover letter .txt" in f.source_a for f in r6_job)
    assert any("Short cover letter .txt" in f.source_a for f in r6_job)

    # 2. Academic dossier missing email_draft
    acad_dir = tmp_path / "PhD_Dossier_NoDraft"
    acad_dir.mkdir()
    (acad_dir / "CV_PhD_en.tex").write_text(
        r"\documentclass{article}\begin{document}PhD CV\end{document}", encoding="utf-8"
    )
    (acad_dir / "CV_PhD_en.pdf").write_bytes(b"%PDF-1.4 mock pdf")
    (acad_dir / "CoverLetter_PhD_en.tex").write_text(
        r"\documentclass{article}\begin{document}PhD Letter\end{document}",
        encoding="utf-8",
    )
    (acad_dir / "CoverLetter_PhD_en.pdf").write_bytes(b"%PDF-1.4 mock pdf")

    res_acad = check_dossier(acad_dir, semantic=False)
    r6_acad = [f for f in res_acad.findings if f.rule == "R6"]
    assert len(r6_acad) >= 1
    assert any("Email draft" in f.source_a for f in r6_acad)


def test_fp7_l2_semantic_receives_enclosed_documents(tmp_path: Path) -> None:
    """FP-7: _run_semantic_pass passes enclosed supporting evidence into corpus."""
    from src.pipeline.coherence import discover_artifacts

    dossier = tmp_path / "Academic_Dossier"
    dossier.mkdir()
    (dossier / "CV_PhD_en.tex").write_text("CV content", encoding="utf-8")
    (dossier / "CoverLetter_PhD_en.tex").write_text(
        "Reference from Prof. Marianne Huchard", encoding="utf-8"
    )
    (dossier / "Recommandations.txt").write_text(
        "Signed by Prof. Marianne Huchard", encoding="utf-8"
    )

    artifacts = discover_artifacts(dossier)
    artifacts.enclosed_docs.append(
        (dossier / "Recommandations.txt", "Signed by Prof. Marianne Huchard")
    )

    # Test that prompt construction includes enclosed doc
    MAX_ENCLOSED_CHARS = 3000
    corpus = []
    for p in [artifacts.cv_tex, artifacts.cl_tex]:
        if p and p.exists():
            corpus.append(f"--- ARTIFACT: {p.name} ---\n" + p.read_text("utf-8"))
    for p, doc_text in artifacts.enclosed_docs:
        corpus.append(
            f"--- ENCLOSED SUPPORTING EVIDENCE: {p.name} ---\n"
            + doc_text[:MAX_ENCLOSED_CHARS]
        )

    full_corpus = "\n\n".join(corpus)
    assert "--- ENCLOSED SUPPORTING EVIDENCE: Recommandations.txt ---" in full_corpus
    assert "Prof. Marianne Huchard" in full_corpus


def test_fp7_l2_semantic_unsupported_claim_without_enclosed_doc_flagged(
    tmp_path: Path,
) -> None:
    """FP-7 TP: Unsupported claim without enclosed document proof remains absent from corpus."""
    from src.pipeline.coherence import discover_artifacts

    dossier = tmp_path / "Academic_Dossier_NoDoc"
    dossier.mkdir()
    (dossier / "CV_PhD_en.tex").write_text("CV content", encoding="utf-8")
    (dossier / "CoverLetter_PhD_en.tex").write_text(
        "Reference from Prof. Unknown Person", encoding="utf-8"
    )

    artifacts = discover_artifacts(dossier)
    corpus = []
    for p in [artifacts.cv_tex, artifacts.cl_tex]:
        if p and p.exists():
            corpus.append(f"--- ARTIFACT: {p.name} ---\n" + p.read_text("utf-8"))
    for p, doc_text in artifacts.enclosed_docs:
        corpus.append(f"--- ENCLOSED SUPPORTING EVIDENCE: {p.name} ---\n" + doc_text)

    full_corpus = "\n\n".join(corpus)
    assert "ENCLOSED SUPPORTING EVIDENCE" not in full_corpus
    assert "Prof. Unknown Person" in full_corpus
