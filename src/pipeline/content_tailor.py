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
    color_theme: str = ""     # Optional sidebar color highlight string
    job_location: str = ""   # City/region extracted from posting (drives \cvlocation selection)


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
  "language": "<fr or en — the language the posting is written in>",
  "variant": "<see variant rules below>",
  "job_location": "<city or region where the job is located, e.g. 'Montpellier', 'Paris', 'Lyon'. Use 'remote' or 'télétravail' if fully remote. Use 'France' if no specific city is mentioned.>",
  "why_this_company": "<2-3 sentences in the SAME language as the posting. \
                        Reference the candidate's ACTUAL experience. \
                        Mention the company's product/tech/industry. Never generic.>",
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
      "highlights": ["<select 2-4 most relevant bullet points from profile for THIS job>"],
      "tech": ["<most relevant tech from that job, max 6>"]
    }}
  ],
  "selected_projects": [
    {{
      "title": "<exact from profile>",
      "period": "<exact from profile>",
      "description": "<exact or lightly reworded to emphasise relevant aspects>",
      "tech": ["<most relevant tech, max 8>"]
    }}
  ]
}}

Selection rules:
- selected_experience: include ALL jobs from the profile (keep them all), but for each job
  choose only the 2-4 highlights most relevant to the job posting.
- selected_projects: include 2-3 projects from the profile most relevant to this job.
  Omit projects with no relevance to the posting.
- cv_summary: MUST follow the requested output language (or posting language if auto).
  4-6 lines. Focus on skills/results matching the posting.
- tailored_skills: ordered by relevance to this job, use exact names from profile.
- All free-text fields MUST follow output language: `why_this_company`, `cv_summary`,
  `selected_experience[*].highlights`, and `selected_projects[*].description`.
  Keep factual meaning unchanged.
- French profile-writing rule to follow strictly:
  "Éviter de mettre des métriques dans ton profil (-70% d'interventions manuelles,
  +500% de vitesse). À réserver pour les expériences professionnelles."
  Therefore, `cv_summary` must NOT contain percentages or uplift/reduction metrics.
- NEVER mention a specific number of years of experience in `cv_summary` or
  `why_this_company` (no "7 ans", "7+ years", "plus de 7 ans", etc.). Describe
  the nature and depth of experience instead.

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

    prompt = ChatPromptTemplate.from_messages(
        [("system", _SYSTEM), ("human", _HUMAN)]
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


def _strip_years_and_metrics(text: str) -> str:
    """Remove years-of-experience mentions and numeric metrics."""
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
