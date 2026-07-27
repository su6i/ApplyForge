"""
content_tailor.py — Extract cover-letter variables from a job posting.

Given the job posting text + the classified role + the candidate's resume
profile, the LLM returns a JSON object with these fields:

    company_name       -> \\CompanyName  (exact name from the posting)
    position_title     -> \\PositionTitle
    language           -> "fr" or "en" (detected from the posting)
    variant            -> "ai"|"it" (French) or "ai"|"python" (English)
    why_this_company   -> 2-3 personalized sentences for \\WhyThisCompany
    match_score        -> 0-100 semantic match between resume and job
    tailored_skills    -> ordered list of candidate's skills most relevant to job
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from src.core.logger import logger
from src.pipeline.role_classifier import RoleType

Language = Literal["fr", "en"]

# Character-limited application portals (e.g. France Travail's "Lettre de
# motivation" text box) cap pasted-in text at 1500 characters.
SHORT_LETTER_CHAR_LIMIT = 1500

class TailoringError(ValueError):
    """Raised when the LLM output cannot be parsed as valid JSON."""
    pass


@dataclass
class TailoredContent:
    company_name: str
    position_title: str
    language: Language
    variant: str              # value that goes into \Variant in the .tex file
    why_this_company: str     # 2-3 sentences, in the detected language
    match_score: int = 0      # 0-100 fitness score
    tailored_skills: list[str] = field(default_factory=list)   # ranked relevant skills
    cv_summary: str = ""      # tailored profile paragraph rewritten for THIS job
    selected_experience: list[dict] = field(default_factory=list)  # [{company,role,period,highlights,tech}]
    selected_projects: list[dict] = field(default_factory=list)    # [{title,period,description,tech}]
    cv_tagline: str = ""      # Short professional tagline for CV header (not the full job title)
    color_theme: str = ""     # Optional sidebar color highlight string
    job_location: str = ""   # City/region extracted from posting (drives \cvlocation selection)
    cl_intro: str = ""        # LLM-generated CL intro paragraph (diplôme + candidature + hook)
    cl_body: list[str] | str = "" # LLM-generated CL body paragraph(s) (key achievement relevant to THIS job)
    cl_short: str = ""        # Standalone plain-text short letter for char-limited portals (e.g. France Travail ≤1500 chars)
    extra_education: list[dict] = field(default_factory=list)  # conditional education entries to add to CV
    selected_education: list[dict] = field(default_factory=list)  # profile education with optional trimmed honors


_SYSTEM = """\
You are a professional CV and cover letter tailoring assistant.
The candidate's full profile (the "life database") is in the CANDIDATE PROFILE
section below. It contains ALL their experiences and projects — more than will
fit on a one-page CV.

Your task: read the job posting carefully, then return a JSON object with
EXACTLY these keys (no extras, no markdown fences):

{{
  "company_name": "<exact company name from the posting>",
  "position_title": "<exact job title from the posting>",
  "cv_tagline": "<short professional title for CV header, 3-5 words max, representing the CANDIDATE's identity adapted to this role — NOT a copy of the job title. E.g. 'Ingénieur Informatique & Réseaux', 'Administrateur Systèmes & Réseaux', 'Développeur Python & Infrastructure'>",
  "language": "<fr or en — the language the posting is written in>",
  "variant": "<see variant rules below>",
  "job_location": "<city or region where the job is located, e.g. 'Montpellier', 'Paris', 'Lyon'. Use 'remote' or 'télétravail' if fully remote. Use 'France' if no specific city is mentioned.>",
  "why_this_company": "<1-2 personalized sentences explaining why the candidate wants to join this company. AT THE END of this paragraph, seamlessly append a short closing statement expressing eagerness for an interview. Do NOT create a separate paragraph for the closing.>",
  "match_score": <integer 0-100>,
  "tailored_skills": [<candidate's skills most relevant to this job, max 10, ranked>],
  "cv_summary": "<one concise paragraph (4-6 lines) rewritten from the profile summary \
                  to highlight experience most relevant to THIS job. \
                  Must be in the requested output language (or posting language if auto). \
                  Must use only the candidate's real experience.>",
  "selected_experience": [
    {{
      "company": "<exact from profile>",
      "location": "<exact from profile — city and country, e.g. 'Montpellier, France'>",
      "role": "<exact from profile>",
      "period": "<exact from profile>",
      "highlights": ["<select 2-3 most relevant bullet points from profile for THIS job>"],
      "tech": ["<most relevant tech from that job, max 6>"]
    }}
  ],
  "selected_projects": [
    {{
      "title": "<exact from profile>",
      "url": "<MUST be exactly the url from profile, never leave empty if it exists>",
      "period": "<exact from profile>",
      "description": "<exact or lightly reworded to emphasise relevant aspects>",
      "tech": ["<most relevant tech, max 8>"]
    }}
  ],
  "selected_education": [
    {{
      "degree": "<exact from profile education>",
      "institution": "<exact from profile education>",
      "period": "<exact from profile education>",
      "honors": "<exact from profile OR trimmed — see space budget rule below>"
    }}
  ],
  "extra_education": [],
  "cl_intro": "<Cover letter paragraph 1 (2-3 sentences). \
                Mention the candidate's diploma/formation. \
                State the candidature for \\PositionTitle at \\CompanyName. \
                Highlight the SPECIFIC skills/background that match THIS job — \
                do NOT use a generic IT or AI paragraph; adapt to the actual job.>",
  "cl_body": ["<First paragraph: pick the SINGLE most relevant project or professional achievement from the CANDIDATE PROFILE for THIS job and detail it concretely — what was built, which technologies, what measurable outcome. Use only real sourced figures.>", "<Second paragraph: pick a DIFFERENT project or experience from the profile that demonstrates a second skill the posting asks for. Never name a project that is not in the CANDIDATE PROFILE. If the job is not software/AI (e.g. network administration, industrial or railway technician), choose the infrastructure/network/automation items instead — do NOT default to AI or RAG projects.>"],
  "cl_short": "<STANDALONE short cover letter, PLAIN TEXT (no LaTeX commands, no markdown, no line-break escapes) for pasting directly into an online application form's character-limited text box (e.g. France Travail caps this at 1500 characters INCLUDING spaces and the greeting/sign-off). Self-contained: opening greeting, one sentence on diploma/candidature for \\PositionTitle at \\CompanyName, ONE concrete relevant achievement (reuse a real sourced figure if one fits, never invent a new one), one short sentence on motivation for THIS company, and a polite closing + your name. STRICT HARD LIMIT: the entire text must be under 1500 characters — write concisely from the start, do not write a long version and expect it to be trimmed.>"
}}

Selection rules:
- Company name consistency (STRICT): pick ONE company/employer name for `company_name`
  and reuse that EXACT same name every time you refer to the employer in `cl_intro` and
  `why_this_company`. If the posting mentions two names (e.g. a legal entity and a
  trading/brand name, or a staffing agency and its end client), pick the one that
  appears to be the actual recruiting/signing employer and use it consistently —
  never switch names mid-letter.
{positioning_bullets}
- `selected_projects`: Select only the most relevant projects. Include 2 projects minimum.
  Translate `title` and `description` to the target language. Rank by relevance to this job.
- cv_summary: MUST follow the requested output language (or posting language if auto).
  4-6 lines. Focus on skills/results matching the posting.
- tailored_skills: ordered by relevance to this job, use exact names from profile.
- All free-text fields MUST follow output language: `why_this_company`, `cv_summary`,
  `selected_experience[*].highlights`, `selected_experience[*].role`,
  `selected_projects[*].description`, `selected_projects[*].title`,
  `selected_education[*].degree`, `selected_education[*].honors`.
  Keep factual meaning unchanged. Do NOT translate company names, institution names, or product names.
- French profile-writing rule to follow strictly:
  "Éviter de mettre des métriques dans ton profil (-70% d'interventions manuelles,
  +500% de vitesse). À réserver pour les expériences professionnelles."
  Therefore, `cv_summary` must NOT contain percentages or uplift/reduction metrics.
- Years of experience rule (STRICT):
  * DEFAULT: never state a total-years-of-experience figure anywhere — not in `cv_summary`,
    not in `cl_intro`, not in `cl_body`, not in `cl_short`, not in `why_this_company` —
    even if such a figure appears in the CANDIDATE PROFILE. Naming a number can only
    self-reject the application against postings that ask for more.
  * Describe seniority through scale and evidence instead (systems operated, users served,
    equipment supervised, criticality of the environment), never through a duration.
  * The ONLY exception is an explicit instruction to the contrary in the rules above; if
    no such instruction is present, no year figure may appear.
  * Never invent, round up, or infer a duration.
- `selected_education`: Always include ALL degrees from the profile's `education` list.
  For `honors`, keep only the 3 most relevant grade items for THIS job — always trim to max 3 items.
  Translate `degree`, `institution`, and `honors` exactly into the requested output language.
- `extra_education`: Always return an empty array [].
- `cv_tagline` MUST be a short professional identity (3-5 words), NOT a copy of the job title.
  It represents WHO the candidate is, not the job they're applying for.
  Bad: "Assistant-e ingénieur informatique instrumentale au sein du Pôle Technologique en Métrologie"
  Good: "Ingénieur Informatique & Réseaux" or "Administrateur Systèmes & Réseaux"
- `cv_summary` MUST NOT start with "Ingénieur X avec un Master en X" or any formulation
  that repeats the same concept twice (e.g. "Ingénieur informatique avec un Master en informatique").
  Prefer: "Diplômé d'un Master en informatique, spécialisé en..." or start directly with the specialization.
- `cl_intro` and `cl_body` MUST be adapted to the actual job domain.
  If the job is not IT/network (e.g. railway maintenance, industrial technician),
  emphasise transferable skills (analysis, troubleshooting, teamwork, technical
  aptitude, rigor) instead of IT-specific tools.

Variant rules:
  If language = "fr":  "ai" or "it"
  If language = "en":  "ai" or "python"

IMPORTANT: Return ONLY the JSON. No explanation, no markdown, no preamble.

{candidate_profile}
"""

_HUMAN = """\
Role type (already classified): {role}
Preferred output language: {preferred_language}

If preferred output language is "fr" or "en":
- Force the JSON field `language` to that exact value.
- Write `why_this_company` and `cv_summary` in that language.
- Write `selected_experience[*].highlights` and `selected_projects[*].description`
  in that language too.
- Keep `variant` compatible with that language.

Job posting:
---
{job_text}
---

Return JSON:"""


def tailor(
  job_text: str,
  role: RoleType,
  resume_profile: str = "",
  preferred_language: Language | str = "",
) -> TailoredContent:
    """
    Extract tailored cover-letter variables from the job posting.

    Parameters
    ----------
    job_text       : Raw text of the job posting.
    role           : Pre-classified canonical role key (e.g. "ai", "devops", "phd").
    resume_profile : Formatted candidate profile text (from resume_loader).
                     If empty, the LLM will work without candidate context.
    """
    logger.debug("Extracting tailored content from job posting…")

    from src.core.llm_factory import get_llm
    llm = get_llm(temperature=0.4)

    system_prompt = _SYSTEM
    if role == "phd":
        system_prompt = system_prompt.replace(
            "more than will\nfit on a one-page CV.",
            "more than will fit on a one-page CV.\nHowever, since this is a PhD application, ignore the 1-page limit and include ALL relevant academic, research, and professional experiences to build a comprehensive multi-page CV."
        )

    from src.core.candidate import load_candidate
    candidate = load_candidate()
    pos_cfg = candidate.get("positioning", {})
    bullets = []
    
    max_exp = pos_cfg.get("max_experience_entries", 0)
    if max_exp > 0:
        bullets.append(f"- selected_experience: include ONLY the candidate's {max_exp} most recent professional position(s). Do NOT list older jobs. (EXCEPTION: for a PhD application include the full history — see the PhD note above.)\n  Rewrite/translate `role` and `highlights` accurately to the target language, maintaining professional terminology.\n  * Adjust highlights to focus heavily on aspects relevant to this specific job.")
    else:
        bullets.append("- selected_experience: include the relevant positions from the profile.\n  Rewrite/translate `role` and `highlights` accurately to the target language, maintaining professional terminology.\n  * Adjust highlights to focus heavily on aspects relevant to this specific job.")

    avoid_titles = pos_cfg.get("avoid_titles", [])
    if avoid_titles:
        bullets.append(f"- NEVER use any of these words in `cv_tagline`: {', '.join(avoid_titles)}. Prefer a title one level above them.")

    avoid_labels = pos_cfg.get("avoid_labels", [])
    if avoid_labels:
        bullets.append(f"- NEVER describe the candidate using any of these terms: {', '.join(avoid_labels)}.")

    framing = pos_cfg.get("framing", "")
    if framing:
        bullets.append(f"- Preferred framing for the candidate: {framing}.")

    if pos_cfg.get("allow_stating_years", False):
        bullets.append("- You MAY state the candidate's real total years of professional experience exactly as given in the CANDIDATE PROFILE. Never inflate it and never invent a figure absent from the profile.")

    allowed_years = _years_exception(candidate, job_text, str(preferred_language or ""), bullets)

    bullets_str = "\n".join(bullets)

    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", _HUMAN)]
    )
    chain = prompt | llm | StrOutputParser()

    truncated = job_text[:8_000]
    raw: str = chain.invoke({
        "job_text": truncated,
        "role": role,
        "candidate_profile": resume_profile,
        "preferred_language": preferred_language or "auto",
        "positioning_bullets": bullets_str,
    })
    logger.debug(f"Raw LLM output: {raw}")

    data = _parse_json(raw)
    known_metrics = _extract_known_metrics(resume_profile)
    content = TailoredContent(
        company_name=data.get("company_name", "Unknown Company"),
        position_title=data.get("position_title", "Unknown Position"),
        language=data.get("language", "fr"),        # type: ignore[arg-type]
        variant=data.get("variant", role),
        why_this_company=_strip_years_and_metrics(data.get("why_this_company", ""), known_metrics, allowed_years),
        match_score=int(data.get("match_score", 0)),
        tailored_skills=data.get("tailored_skills", []),
        cv_summary=_strip_years_and_metrics(data.get("cv_summary", ""), known_metrics, allowed_years),
        selected_experience=data.get("selected_experience", []),
        selected_projects=data.get("selected_projects", []),
        job_location=data.get("job_location", ""),
        cl_intro=_strip_years_and_metrics(data.get("cl_intro", ""), known_metrics, allowed_years),
        cl_body=_strip_years_and_metrics(data.get("cl_body", ""), known_metrics, allowed_years),
        cl_short=_enforce_char_limit(
            _strip_years_and_metrics(data.get("cl_short", ""), known_metrics, allowed_years)
        ),
        extra_education=data.get("extra_education", []),
        selected_education=data.get("selected_education", []),
        cv_tagline=data.get("cv_tagline", ""),
    )
    logger.info(
        f"Tailored → company={content.company_name!r}, "
        f"title={content.position_title!r}, lang={content.language}, "
        f"variant={content.variant!r}, match_score={content.match_score}, "
        f"job_location={content.job_location!r}"
    )
    if content.match_score < 40:
        logger.warning(
            f"Low match score ({content.match_score}/100) for {content.position_title!r} "
            f"at {content.company_name!r}. Consider skipping this application."
        )
    return content


def _parse_json(raw: str) -> dict:
    """Parse LLM output, handling common wrapping patterns."""
    # Strip potential markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        snippet = raw[:300]
        logger.error(f"JSON parse error: {exc}. Raw text (truncated): {snippet}")
        raise TailoringError(f"Failed to parse LLM output as JSON: {exc}. Snippet: {snippet}") from exc


def _extract_known_metrics(source_text: str) -> set[str]:
    """Collect every sourced percentage figure (bare digits) from the candidate
    profile text, so real numbers survive stripping even if the LLM drops the
    '~' marker while paraphrasing (e.g. rewriting "~80%" as plain "80%")."""
    if not source_text:
        return set()
    return set(re.findall(r"\d+[\.,]?\d*(?=\s*%)", source_text))


_YEAR_FIGURE_RE = re.compile(r"\b(\d{1,2})\s*\+?\s*(?:ans?|années?|years?)\b", re.IGNORECASE)
_EXPERIENCE_WORD_RE = re.compile(r"exp[ée]rience|experience|\bexp\.", re.IGNORECASE)


def _posting_required_years(job_text: str) -> int | None:
    """Return the years-of-experience figure the posting explicitly demands, else None.

    A bare "2 ans" is not a requirement — it is just as likely a contract length
    ("CDD de 2 ans") or a company age. Only a figure sitting within a short window
    of the word "expérience"/"experience" is treated as a demand. When a posting
    names several (e.g. "3 ans minimum, 5 ans idéalement"), the highest is taken:
    the caller caps it against the candidate's real window, so this can never
    produce an overclaim, only the best honest answer to what was asked.
    """
    if not job_text:
        return None
    found: list[int] = []
    for match in _YEAR_FIGURE_RE.finditer(job_text):
        window = job_text[max(0, match.start() - 60): match.end() + 60]
        if _EXPERIENCE_WORD_RE.search(window):
            found.append(int(match.group(1)))
    return max(found) if found else None


def _scale_phrases(evidence: dict, preferred_language: str) -> list[str]:
    """Pick the `cv_evidence.scale` phrases for the output language.

    Accepts either a flat list (language-agnostic) or a {lang: [...]} mapping,
    because the vault is hand-edited and both shapes read naturally there.
    """
    scale = evidence.get("scale") or []
    if isinstance(scale, list):
        return [str(item) for item in scale]
    lang = (preferred_language or "").strip().lower()
    for key in (lang, "fr", "en"):
        if key and scale.get(key):
            return [str(item) for item in scale[key]]
    return []


def _years_exception(
    candidate: dict,
    job_text: str,
    preferred_language: str,
    bullets: list[str],
) -> int | None:
    """Decide whether a year figure may appear at all, appending the matching
    prompt rules to ``bullets``. Returns the one figure allowed to survive
    post-processing, or None when no duration may be stated.

    The default is silence: naming a total only self-rejects against postings
    asking for more. A figure is unlocked only when the posting itself demands
    one, and even then it is capped at the candidate's real countable window —
    so the answer is always "exactly what you asked for, and I have it", never
    an inflated career total.
    """
    evidence = candidate.get("cv_evidence") or {}

    phrases = _scale_phrases(evidence, preferred_language)
    if phrases:
        bullets.append(
            "- Convey seniority through scale, never through a duration. Reuse these "
            "real facts from the candidate's record when they fit the posting, and "
            "invent no others: " + " | ".join(phrases)
        )

    window = evidence.get("countable_window") or {}
    window_years = int(window.get("years") or 0)
    if window_years <= 0:
        return None

    asked = _posting_required_years(job_text)
    if not asked:
        return None

    allowed = min(asked, window_years)
    span = ""
    if window.get("from_year") and window.get("to_year"):
        span = f" ({window['from_year']}–{window['to_year']})"
    bullets.append(
        f"- This posting explicitly asks for {asked} year(s) of experience. You MAY — once, "
        f"in `cl_intro` or `cv_summary`, not in both — write exactly "
        f"\"{allowed} ans d'expérience{span}\" (French) or \"{allowed} years of experience{span}\" "
        f"(English). Any other duration anywhere in the output is forbidden."
    )
    logger.info(
        f"Years exception unlocked: posting asks {asked}, countable window {window_years} "
        f"-> stating {allowed}."
    )
    return allowed


def _strip_metrics_in_summary(text: str, known_metrics: set[str] | None = None) -> str:
    """Remove fabricated numeric performance metrics from generated text.

    A metric is kept if its digits match a genuine figure from the source
    profile (``known_metrics``) — regardless of whether the LLM reproduced the
    '~' marker — or, failing that, if it's still tilde-prefixed in the output.
    Anything else is treated as fabricated and stripped. When stripping, also
    consume an immediately preceding French/English connector (de, d', à, by,
    of) to keep the sentence grammatical.
    """
    if not text:
        return text
    known_metrics = known_metrics or set()

    # Pattern: optional connector, optional tilde, optional sign, digits, optional decimal, optional % sign
    # The connector group (de/d'/à/by/of) is captured so we can drop it with the metric.
    pattern = r"(?P<connector>(?:de\s+|d['\u2019]|à\s+|by\s+|of\s+))?(?P<tilde>~)?\b[+-]?(?P<digits>\d+[\.,]?\d*)\s*%"

    def _replace(match: re.Match) -> str:
        if match.group("tilde") or match.group("digits") in known_metrics:
            return match.group(0)  # keep entire match including connector
        return ""  # remove metric and connector

    cleaned = re.sub(pattern, _replace, text, flags=re.IGNORECASE)
    # Clean up resulting whitespace and punctuation artifacts
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,;.!?])", r"\1", cleaned)  # remove space before punctuation
    cleaned = re.sub(r",\s*,", ",", cleaned)  # remove double commas
    return cleaned.strip()


def _enforce_char_limit(text: str, limit: int = SHORT_LETTER_CHAR_LIMIT) -> str:
    """Hard safety net for portals with a strict character cap: the prompt asks
    the LLM to stay under `limit`, but don't trust it blindly. If it overruns,
    cut at the last sentence boundary before the limit (falling back to a hard
    cut if no boundary is found early enough) rather than truncating mid-word.
    """
    if not text or len(text) <= limit:
        return text
    truncated = text[:limit]
    boundary = max(truncated.rfind(". "), truncated.rfind(".\n"), truncated.rfind("! "), truncated.rfind("? "))
    if boundary > limit * 0.6:
        truncated = truncated[: boundary + 1]
    return truncated.rstrip()


def _strip_years_and_metrics(
    text: str | list[str],
    known_metrics: set[str] | None = None,
    allowed_years: int | None = None,
) -> str | list[str]:
    """Remove years-of-experience mentions and fabricated numeric metrics.
    Logs a warning when any modification is made.

    ``allowed_years`` is the single figure the posting explicitly asked for and
    that the candidate genuinely covers (see ``_posting_required_years`` and
    ``cv_evidence.countable_window``). That exact figure survives; every other
    duration is still removed, so the model cannot smuggle a different number
    through by claiming the posting authorised it.
    """
    if isinstance(text, list):
        return [_strip_years_and_metrics(t, known_metrics, allowed_years) for t in text]  # type: ignore
    if not text:
        return text
    original = text

    def _drop_unless_allowed(match: re.Match) -> str:
        if allowed_years is not None and int(match.group("digits")) == allowed_years:
            return match.group(0)
        return ""

    # French year patterns: remove only the quantified phrase
    # Matches optional leading connector (avec/plus de/environ/près de), then digits, optional +, "an" or "ans", optional rest like " d'expérience"
    # Consume the phrase entirely, including any following space or period boundary.
    fr_pattern = r"(?:plus de\s+|environ\s+|près de\s+|avec\s+)?(?P<digits>\d+)\s*\+?\s*ans?(?:\s+d['\u2019](?:expérience|exp\.?))?"
    cleaned = re.sub(fr_pattern, _drop_unless_allowed, text, flags=re.IGNORECASE)
    # English year patterns
    en_pattern = r"(?:more than\s+|over\s+|about\s+|with\s+)?(?P<digits>\d+)\s*\+?\s*years?(?:\s+of\s+experience|\s+experience)?"
    cleaned = re.sub(en_pattern, _drop_unless_allowed, cleaned, flags=re.IGNORECASE)
    # Remove fabricated % metrics — real, sourced figures survive (handled below).
    cleaned = _strip_metrics_in_summary(cleaned, known_metrics)
    # Clean up whitespace and punctuation
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,;.!?])", r"\1", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = cleaned.strip()
    # Remove leading commas/connectors
    cleaned = re.sub(r"^[,\s]+", "", cleaned).strip()
    if cleaned != original and original != "":
        logger.warning(f"_strip_years_and_metrics modified text:\n  BEFORE: {original!r}\n  AFTER:  {cleaned!r}")
    return cleaned
