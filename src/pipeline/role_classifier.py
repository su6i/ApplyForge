"""
role_classifier.py — Classify a job posting into one of three CV tracks.

Output is one of:
    "ai"   → AI Engineer / Data Scientist / ML / Python Developer
    "it"   → IT Support / Network / SysAdmin / Infrastructure
    "phd"  → PhD / Research / Academic positions

Uses an LLM with a tightly constrained prompt so classification is deterministic.
"""
from __future__ import annotations

from typing import Literal

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from src.core.logger import logger
RoleType = Literal["ai", "it", "phd"]

_VALID = {"ai", "it", "phd"}

_SYSTEM = """\
You are a CV routing assistant. Given a job posting, decide which of the
following three CV profiles best matches the position:

  ai   → AI Engineer, Data Scientist, Data Analyst, Machine Learning,
          NLP, LLM, Python Developer, Backend Developer, MLOps
  it   → IT Support, Helpdesk, Network Technician, SysAdmin,
          Infrastructure, VOIP, Cisco, Windows/Linux administration
  phd  → PhD, Postdoc, Research Fellow, Academic, University position,
          grant-funded research

Rules:
- Reply with EXACTLY ONE word: ai, it, or phd. Nothing else.
- Default to "ai" if genuinely ambiguous between ai and another category.
- Never explain your answer.
"""

_HUMAN = """\
Job posting:
---
{job_text}
---
Reply with one word (ai / it / phd):"""


def classify(job_text: str) -> RoleType:
    """
    Classify the job posting text into 'ai', 'it', or 'phd'.

    Falls back to 'ai' if the LLM returns unexpected output.
    """
    logger.debug("Classifying job role from posting text…")

    from src.core.llm_factory import get_llm
    llm = get_llm(temperature=0, max_tokens=10)

    prompt = ChatPromptTemplate.from_messages(
        [("system", _SYSTEM), ("human", _HUMAN)]
    )
    chain = prompt | llm | StrOutputParser()

    # Truncate to avoid token overflow; first 6 000 chars covers most postings.
    truncated = job_text[:6_000]
    raw: str = chain.invoke({"job_text": truncated}).strip().lower()

    role: RoleType = raw if raw in _VALID else "ai"  # type: ignore[assignment]
    logger.info(f"Role classified as: {role!r}  (raw LLM output: {raw!r})")
    return role
