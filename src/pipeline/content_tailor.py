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
  "cv_tagline": "<short professional title for CV header, 3-5 words max, representing the CANDIDATE's identity adapted to this role — NOT a copy of the job title. E.g. 'Ingénieur Informatique & Réseaux', 'Technicien Systèmes & Automatisation', 'Développeur Python & Infrastructure'>",
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
  "cl_body": ["<First paragraph: Detail the 'toHero' RAG and document analysis project.>", "<Second paragraph: Detail the multi-agent architecture projects ('ApplyForge', 'Su6i-Yar', or custom elevator project). Adapt the descriptions to match the required skills of THIS job.>"]
}}

Selection rules:
- selected_experience: You MUST include ALL jobs from the `experience` list. Do NOT drop any job.
  Rewrite/translate `role` and `highlights` accurately to the target language, maintaining professional terminology.
  * Adjust highlights to focus heavily on aspects relevant to this specific job.
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
  * DEFAULT: NEVER mention a specific number of years. Describe depth/nature instead.
  * EXCEPTION: IF the job posting explicitly requires N years (e.g. "3 ans d'expérience
    minimum"), AND the candidate has at least N relevant years in that domain,
    THEN you MAY write exactly N years (not more) in `cl_intro` or `cv_summary`.
  * Never invent years not requested. Never exceed the number asked.
- `selected_education`: Always include ALL degrees from the profile's `education` list.
  For `honors`, keep only the 3 most relevant grade items for THIS job — always trim to max 3 items.
  Translate `degree`, `institution`, and `honors` exactly into the requested output language.
- `extra_education`: Always return an empty array [].
- `cv_tagline` MUST be a short professional identity (3-5 words), NOT a copy of the job title.
  It represents WHO the candidate is, not the job they're applying for.
  Bad: "Assistant-e ingénieur informatique instrumentale au sein du Pôle Technologique en Métrologie"
  Good: "Ingénieur Informatique & Réseaux" or "Technicien Systèmes & Automatisation"
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
    role           : Pre-classified role type ("ai", "it", "phd").
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
    })
    logger.debug(f"Raw LLM output: {raw}")

    data = _parse_json(raw)
    content = TailoredContent(
        company_name=data.get("company_name", "Unknown Company"),
        position_title=data.get("position_title", "Unknown Position"),
        language=data.get("language", "fr"),        # type: ignore[arg-type]
        variant=data.get("variant", role),
        why_this_company=_strip_years_and_metrics(data.get("why_this_company", "")),
        match_score=int(data.get("match_score", 0)),
        tailored_skills=data.get("tailored_skills", []),
        cv_summary=_strip_years_and_metrics(data.get("cv_summary", "")),
        selected_experience=data.get("selected_experience", []),
        selected_projects=data.get("selected_projects", []),
        job_location=data.get("job_location", ""),
        cl_intro=_strip_years_and_metrics(data.get("cl_intro", "")),
        cl_body=_strip_years_and_metrics(data.get("cl_body", "")),
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
        logger.error(f"JSON parse error: {exc}\nRaw text:\n{raw}")
        return {}


def _strip_metrics_in_summary(text: str) -> str:
    """Remove numeric performance metrics from profile summary paragraph."""
    if not text:
        return text
    cleaned = re.sub(r"[+-]?\d+[\.,]?\d*\s*%", "", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _strip_years_and_metrics(text: str | list[str]) -> str | list[str]:
    """Remove years-of-experience mentions and numeric metrics."""
    if isinstance(text, list):
        return [_strip_years_and_metrics(t) for t in text] # type: ignore
    if not text:
        return text
    # Remove patterns like "7 ans d'expérience", "plus de 7 ans", "7+ years", "more than 7 years"
    cleaned = re.sub(
        r"\b(plus de |more than |over )?\d+\+?\s+an[ns]?\b[^,.]*(d['']expérience|d'exp\.?)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b(plus de |more than |over )?\d+\+?\s+years?\b[^,.]*",
                     "", cleaned, flags=re.IGNORECASE)
    # Remove numeric % metrics
    cleaned = re.sub(r"[+-]?\d+[\.,]?\d*\s*%", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    # Remove leftover sentence fragments starting with comma/and
    cleaned = re.sub(r"^[,\s]+", "", cleaned)
    return cleaned
