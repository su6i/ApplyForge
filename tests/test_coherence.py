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

from src.pipeline.coherence import check_dossier


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
    (app_dir / "cv-owner-LettreMotivation_Support_fr.tex").write_text(cl_tex, encoding="utf-8")
    (app_dir / "cv-owner-LettreMotivation_Support_fr.txt").write_text(cl_full, encoding="utf-8")
    (app_dir / "cv-owner-LettreMotivation_Courte_Support_fr.txt").write_text(cl_short, encoding="utf-8")

    # Touch PDFs after TEX so mtimes are clean
    time.sleep(0.02)
    (app_dir / "cv-owner-CV_Support_fr.pdf").write_bytes(b"%PDF-1.4 dummy")
    (app_dir / "cv-owner-LettreMotivation_Support_fr.pdf").write_bytes(b"%PDF-1.4 dummy")

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
    cv_tex_no_du = cv_tex.replace(r"\cvevent{DU Big Data, Data Science}{Université de Montpellier}{2021-2022}{}", "")
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
    text_bad = text.replace("Support pour 1 500 utilisateurs.", "J'ai déployé des tableaux de bord Power BI utilisés par 1 500+ utilisateurs.")
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
    cl_tex.write_text(cl_tex.read_text(encoding="utf-8").replace("DU Big Data", "Doctorat en IA"), encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R2" and "Doctorat" in f.message for f in result.findings)


def test_rule_r3_diploma_contradiction(tmp_path: Path) -> None:
    """R3 fires when letter degree framing contradicts CV profile framing."""
    dossier = _create_clean_dossier(tmp_path)
    # CV profile emphasizes DU Big Data without Master; letter frames primary degree as Master without DU
    cv_tex = dossier / "cv-owner-CV_Support_fr.tex"
    cv_tex.write_text(cv_tex.read_text(encoding="utf-8").replace("Master en Informatique", "DUT"), encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R3" or f.rule == "R2" for f in result.findings)


def test_rule_r4_metric_support(tmp_path: Path) -> None:
    """R4 fires when metric in letter is completely missing from CV."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt.write_text(cl_txt.read_text(encoding="utf-8") + "\nGéré 922 000 requêtes API.", encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R4" and "922" in f.message for f in result.findings)


def test_rule_r5_identity(tmp_path: Path) -> None:
    """R5 fires when company name differs between CV .tex and Letter .tex."""
    dossier = _create_clean_dossier(tmp_path)
    cl_tex = dossier / "cv-owner-LettreMotivation_Support_fr.tex"
    cl_tex.write_text(cl_tex.read_text(encoding="utf-8").replace(r"\newcommand{\CompanyName}{Acme Corp}", r"\newcommand{\CompanyName}{Other Corp}"), encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R5" and "CompanyName" in f.message or "company" in f.message for f in result.findings)


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
    cl_txt.write_text(cl_txt.read_text(encoding="utf-8") + "\nسلام دنیا", encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R7" and "Persian" in f.message for f in result.findings)


def test_rule_r8_no_placeholder(tmp_path: Path) -> None:
    """R8 fires when unfilled placeholder like [Company Name] or [...] is found."""
    dossier = _create_clean_dossier(tmp_path)
    cl_txt = dossier / "cv-owner-LettreMotivation_Support_fr.txt"
    cl_txt.write_text(cl_txt.read_text(encoding="utf-8").replace("Acme Corp", "[Company Name]"), encoding="utf-8")

    result = check_dossier(dossier)
    assert not result.passed
    assert any(f.rule == "R8" and "[Company Name]" in f.quote_a for f in result.findings)


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
    cl_tex = cl_tex_path.read_text(encoding="utf-8").replace("du DU Big Data", "du Diplôme d'Université en Big Data")
    cl_tex_path.write_text(cl_tex, encoding="utf-8")
    cl_txt = cl_txt_path.read_text(encoding="utf-8").replace("du DU Big Data", "du Diplôme d'Université en Big Data")
    cl_txt_path.write_text(cl_txt, encoding="utf-8")
    cl_short = cl_short_path.read_text(encoding="utf-8").replace("du DU Big Data", "du Diplôme d'Université en Big Data")
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
    cl_tex_with_comment = "% ⚠️ DO NOT leave any placeholder brackets [...] in the final version.\n" + cl_tex
    cl_tex_path.write_text(cl_tex_with_comment, encoding="utf-8")

    result = check_dossier(dossier)
    r8_findings = [f for f in result.findings if f.rule == "R8"]
    assert len(r8_findings) == 0

