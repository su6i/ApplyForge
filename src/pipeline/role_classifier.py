"""
role_classifier.py — Classify a job posting into one CV track.

The set of valid tracks and their descriptions come entirely from the Roles
Registry (``config/roles.yaml`` via ``src.core.roles``). Output is one canonical
role key (e.g. "general", "devops", "ai", "phd").

Uses an LLM with a tightly constrained prompt so classification is deterministic.
"""
from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.core import roles as roles_registry
from src.core.logger import logger

# RoleType is now an open string validated at runtime against the registry
# (the old Literal["ai","it","phd"] is gone — roles live in config/roles.yaml).
RoleType = str

_VALID = set(roles_registry.classifier_keys())

_SYSTEM = f"""\
You are a CV routing assistant. Given a job posting, decide which of the
following CV profiles best matches the position:

{roles_registry.classifier_descriptions()}

Rules:
- Reply with EXACTLY ONE word, one of: {", ".join(roles_registry.canonical_keys())}. Nothing else.
- Default to "{roles_registry.default_role()}" if genuinely ambiguous.
- Never explain your answer.
"""

_HUMAN = """\
Job posting:
---
{job_text}
---
Reply with one word ({valid}):"""


def classify(job_text: str) -> RoleType:
    """
    Classify the job posting text into one canonical role key.

    Falls back to the registry's ``default_role`` if the LLM returns unexpected
    output. Aliases the model might emit (e.g. legacy "it") are resolved to the
    canonical key.
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
    raw: str = chain.invoke(
        {"job_text": truncated, "valid": " / ".join(roles_registry.canonical_keys())}
    ).strip().lower()

    role: RoleType = roles_registry.resolve(raw) or roles_registry.default_role()
    logger.info(f"Role classified as: {role!r}  (raw LLM output: {raw!r})")
    return role
