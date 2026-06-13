"""
service.py — ApplicationService: the single public interface for the pipeline.

Usage:
    service = ApplicationService()
    bundle = service.generate(job_url="https://...")
    # bundle.cv_pdf, bundle.cl_pdf, bundle.output_dir, bundle.match_score

The service automatically loads `data/resume_profile.json` and injects it
into the LLM prompt so the generated content is grounded in the candidate's
actual experience.  If the job match score is below `min_match_score`, a
warning is raised (but generation continues — the caller decides what to do).
"""
from __future__ import annotations

import json
import re
import requests
from copy import deepcopy
from pathlib import Path

from src.core.logger import logger
from src.core.llm_factory import get_llm
from src.core.settings import CV_OWNER_SLUG, REPO_ROOT
from src.pipeline.content_tailor import TailoredContent, tailor
from src.pipeline.job_scraper import JobPosting, scrape
from src.pipeline.latex_builder import ApplicationBundle, build
from src.pipeline.resume_loader import format_for_prompt, load_profile
from src.pipeline.role_classifier import RoleType, classify
from src.pipeline import technicien_adapter

# Default: warn (but don't abort) when match score is below this threshold.
DEFAULT_MIN_MATCH = 40
GENERATED_PROFILES_DIR = REPO_ROOT / "data"

_ROLE_LABEL_MAP = {
    "ai": "AI",
    "it": "IT",
    "phd": "PhD",
    "python": "Python",
    "devops": "DevOps",
}


class ApplicationService:
    """
    Orchestrates the full pipeline:
        URL  →  scrape  →  classify  →  tailor (with resume context)
            →  quality check  →  build LaTeX  →  PDFs

    All quality guards run automatically — the caller never needs to invoke
    verify.py or any separate check step.
    """

    def __init__(self, min_match_score: int = DEFAULT_MIN_MATCH) -> None:
        self.min_match_score = min_match_score

    def generate(
        self,
        job_url: str,
        template: str = "altacv",
        color: str = "",
        output_language: str = "auto",
        include_licence: bool = False,
    ) -> ApplicationBundle:
        """
        Given a job URL, produce a tailored CV + cover letter PDF pair.

        Parameters
        ----------
        job_url : Full URL of the job posting.

        Returns
        -------
        ApplicationBundle with .cv_pdf, .cl_pdf, .output_dir, and .match_score.

        Raises
        ------
        RuntimeError  if the page text cannot be extracted.
        """
        # 1 — Fetch job page
        logger.info(f"[1/4] Scraping: {job_url}")
        posting: JobPosting = scrape(job_url)
        if not posting.body:
            raise RuntimeError(
                f"Could not extract text from the job URL: {job_url}"
            )

        # Availability guard — abort early if the posting has been taken down.
        _EXPIRED_SIGNALS = [
            "plus disponible", "offre expirée", "offre clôturée",
            "offre retirée", "n'est plus disponible",
            "this job is no longer available", "not available",
        ]
        body_lower = posting.body.lower()
        if any(sig in body_lower for sig in _EXPIRED_SIGNALS):
            raise RuntimeError(
                f"Job posting appears to be expired or no longer available: {job_url}"
            )

        # Apply URL guard — check the direct application link, not just the job listing.
        if posting.apply_url and posting.apply_url != job_url:
            logger.info(f"Checking apply URL: {posting.apply_url}")
            try:
                _headers = {"User-Agent": "Mozilla/5.0 (compatible; ApplyForge/1.0)"}
                apply_resp = requests.get(
                    posting.apply_url, headers=_headers, timeout=15, allow_redirects=True
                )
                if apply_resp.status_code >= 400:
                    raise RuntimeError(
                        f"⛔  Application link is unreachable (HTTP {apply_resp.status_code}): "
                        f"{posting.apply_url}"
                    )
                apply_body_lower = apply_resp.text.lower()
                if any(sig in apply_body_lower for sig in _EXPIRED_SIGNALS):
                    raise RuntimeError(
                        f"⛔  Application link appears expired or closed: {posting.apply_url}"
                    )
            except RuntimeError:
                raise
            except Exception as exc:
                logger.warning(f"Could not verify apply URL {posting.apply_url}: {exc}")

        # Eligibility guards — hard blockers for this candidate profile.
        _BLOCKERS: list[tuple[list[str], str]] = [
            (
                ["permis b obligatoire", "permis de conduire obligatoire",
                 "permis b exigé", "permis b requis", "permis b indispensable",
                 "driving license required", "driver's license required"],
                "⛔  Permis B obligatoire — le candidat n'a pas de permis de conduire.",
            ),
            (
                ["être fonctionnaire", "titulaire de la fonction publique",
                 "réservé aux agents titulaires", "fonctionnaire de catégorie",
                 "mutation interne", "détachement uniquement"],
                "⛔  Poste réservé aux fonctionnaires titulaires — candidat non-fonctionnaire.",
            ),
            (
                ["nationalité française obligatoire", "réservé aux ressortissants français",
                 "nationalité française exigée", "être de nationalité française"],
                "⛔  Nationalité française obligatoire — candidat de nationalité iranienne.",
            ),
            (
                ["habilitation secret défense", "habilitation confidentiel défense",
                 "secret-défense", "accès à des informations classifiées secret"],
                "⛔  Habilitation Secret/Confidentiel Défense requise — nécessite la nationalité française.",
            ),
        ]
        for signals, message in _BLOCKERS:
            if any(sig in body_lower for sig in signals):
                raise RuntimeError(f"{message} Aucun CV généré.")

        # 2 — Classify role
        logger.info("[2/4] Classifying role…")
        role: RoleType = classify(posting.body)

        # Load profile dynamically using the resolved role
        _master_lang = output_language.strip().lower() if output_language and output_language != "auto" else "en"
        try:
            resume_profile_str: str = format_for_prompt(role, lang=_master_lang)
            profile_dict: dict = load_profile(role, lang=_master_lang)
        except Exception as exc:
            logger.warning(f"Could not load profile: {exc}")
            resume_profile_str = ""
            profile_dict = {}

        # 3 — Tailor cover letter content (resume profile injected here)
        logger.info("[3/4] Tailoring content with resume profile…")
        content: TailoredContent = tailor(
            posting.body,
            role,
            resume_profile=resume_profile_str,
            preferred_language=output_language,
        )
        content.color_theme = color or profile_dict.get("color_theme", "")

        # --licence flag: explicitly inject the conditional Bachelor's degree.
        if include_licence:
            cond_edu = profile_dict.get("conditional_education") or []
            if cond_edu:
                content.extra_education = list(cond_edu)
                logger.info(f"--licence: injecting {len(cond_edu)} conditional education entries")

        # Optional hard override from CLI/API: force output language.
        forced_lang = output_language.strip().lower()
        if forced_lang and forced_lang != "auto":
            content.language = forced_lang  # type: ignore[assignment]

            # Keep cover letter variant consistent with target language.
            if forced_lang == "fr" and content.variant == "python":
                content.variant = "ai" if role == "ai" else "it"
            elif forced_lang == "en" and content.variant == "it":
                content.variant = "ai" if role == "ai" else "python"

        if content.match_score < self.min_match_score:
            logger.warning(
                f"⚠  Match score {content.match_score}/100 is below threshold "
                f"({self.min_match_score}). Proceeding anyway — review before sending."
            )

        target_lang = str(content.language).strip().lower() if content.language else "en"
        if not target_lang:
            target_lang = "en"
        profile_for_build = _resolve_profile_variant(
            role=role,
            output_language=target_lang,
            position_title=content.position_title,
            source_profile=profile_dict,
            use_llm_translation=True,
        )

        # Technicien-tier adapter — deterministic post-processing, no LLM.
        if technicien_adapter.is_technicien_tier(posting.body):
            logger.info("Technicien tier detected — applying deterministic adapter (drop DU, filter honors, normalize titles)")
            profile_for_build, content = technicien_adapter.apply(profile_for_build, content)

        # 4 — Compile LaTeX (CV generated dynamically from profile + LLM selections)
        logger.info("[4/4] Building PDF bundle…")
        bundle: ApplicationBundle = build(
            role,
            content,
            profile=profile_for_build,
            template=template,
            job_posting=posting,
            job_url=job_url,
        )

        logger.info(
            f"Application generated:\n"
            f"  CV          : {bundle.cv_pdf}\n"
            f"  Cover letter: {bundle.cl_pdf}\n"
            f"  Folder      : {bundle.output_dir}\n"
            f"  Match score : {content.match_score}/100\n"
            f"  Top skills  : {', '.join(content.tailored_skills[:5])}"
        )
        return bundle

    def preview(
        self,
        template: str = "altacv",
        role: RoleType = "it",
        color: str = "",
        output_language: str = "fr",
        localize_preview: bool = True,
    ) -> ApplicationBundle:
        """
        Generate a preview CV (no LLM tailoring, using full profile data).
        Useful for checking template layout and formatting.
        """
        logger.info(f"Generating preview: role={role}, template={template}")
        
        try:
            profile_dict = load_profile(role)
        except Exception as e:
            logger.warning(f"Could not load profile: {e}")
            profile_dict = {}

        preview_lang = output_language.strip().lower()
        if not preview_lang:
            preview_lang = "fr"

        if localize_preview and profile_dict:
            preview_title = profile_dict.get("identity", {}).get("title", role)
            profile_dict = _resolve_profile_variant(
                role=role,
                output_language=preview_lang,
                position_title=preview_title,
                source_profile=profile_dict,
                use_llm_translation=True,
            )

        # Create a dummy TailoredContent that mostly points back to profile defaults
        content = TailoredContent(
            company_name="Preview Company",
            position_title=profile_dict.get("identity", {}).get("title", "AI/Data Engineer"),
            language=preview_lang,  # type: ignore[arg-type]
            variant=role,
            why_this_company="This is a preview of how your CV looks with the selected template.",
            match_score=100,
            # Empty lists will trigger renderers to fallback to full profile data
            tailored_skills=[],
            cv_summary="",
            selected_experience=[],
            selected_projects=[],
            color_theme=color,
        )

        bundle: ApplicationBundle = build(role, content, profile=profile_dict, template=template)
        return bundle

    def generate_spontaneous(
        self,
        role: str,
        city: str = "",
        language: str = "",
    ) -> ApplicationBundle:
        """
        Generate a spontaneous application CV (candidature spontanée).

        Uses the pre-written static template for the given role — no LLM tailoring.
        Personal data is injected via templates/shared/personal_data.tex at compile time.

        Parameters
        ----------
        role     : Role key (e.g., "ai", "ai-en", "phd", "devops-alternance", "polyvalent").
                   Run with role="?" to see available keys.
        city     : Location hint — pass "montpellier" or any Occitanie city to get
                   "Montpellier, mobile en France"; leave empty for Grenoble (default).
        language : Override output language ("fr" or "en"). Empty → template default.
        """
        from src.pipeline.latex_builder import _SPONTANEOUS_MAP, build_spontaneous

        if role == "?":
            available = sorted(_SPONTANEOUS_MAP.keys())
            raise ValueError(f"Available spontaneous roles: {', '.join(available)}")

        logger.info(f"Generating spontaneous CV: role={role!r}, city={city!r}")
        bundle = build_spontaneous(role_key=role, city=city, language=language)
        logger.info(f"Spontaneous CV ready: {bundle.cv_pdf}")
        return bundle

    def generate_with_llm_fallback(
        self,
        job_url: str,
        template: str = "altacv",
        color: str = "",
        output_language: str = "auto",
        enable_fallback: bool = True,
        include_licence: bool = False,
    ) -> tuple[ApplicationBundle | None, str, bool]:
        """
        Generate application with LLM translation first, fallback to offline if LLM fails.

        Returns
        -------
        Tuple of (bundle, error_message, used_fallback)
        - bundle: ApplicationBundle if successful, else None
        - error_message: descriptive error string if LLM failed (empty if success)
        - used_fallback: True if offline dictionary was used, False otherwise

        If LLM fails and enable_fallback=False, returns (None, error_msg, False).
        If LLM fails and enable_fallback=True, returns (bundle, error_msg, True) using offline.
        """
        try:
            logger.info("Attempting LLM-based generation...")
            bundle = self.generate(
                job_url=job_url,
                template=template,
                color=color,
                output_language=output_language,
                include_licence=include_licence,
            )
            return bundle, "", False  # Success, no error, no fallback
        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"LLM-based generation failed: {error_msg}")
            
            if not enable_fallback:
                return None, error_msg, False
            
            logger.info("Attempting offline dictionary-based fallback...")
            try:
                bundle = self._generate_with_offline_translation(
                    job_url=job_url,
                    template=template,
                    color=color,
                    output_language=output_language,
                )
                return bundle, error_msg, True  # Fallback succeeded
            except Exception as fallback_exc:
                fallback_msg = str(fallback_exc)
                logger.error(f"Offline fallback also failed: {fallback_msg}")
                return None, f"{error_msg}\nOffline fallback failed: {fallback_msg}", True

    def _generate_with_offline_translation(
        self,
        job_url: str,
        template: str = "altacv",
        color: str = "",
        output_language: str = "auto",
    ) -> ApplicationBundle:
        """
        Fallback generation using offline dictionary translation instead of LLM.
        Uses the same pipeline but applies deterministic regex/phrase replacement.
        """
        # 1 — Fetch job page
        logger.info(f"[Offline] [1/4] Scraping: {job_url}")
        posting: JobPosting = scrape(job_url)
        if not posting.body:
            raise RuntimeError(
                f"Could not extract text from the job URL: {job_url}"
            )

        # 2 — Classify role
        logger.info("[Offline] [2/4] Classifying role…")
        role: RoleType = classify(posting.body)

        # Load profile dynamically
        try:
            resume_profile_str: str = format_for_prompt(role)
            profile_dict: dict = load_profile(role)
        except Exception as exc:
            logger.warning(f"Could not load profile: {exc}")
            resume_profile_str = ""
            profile_dict = {}

        # 3 — Use offline dictionary to tailor instead of LLM
        logger.info("[Offline] [3/4] Tailoring with offline dictionary…")
        content: TailoredContent = _tailor_offline(
            posting.body,
            role,
            profile_dict=profile_dict,
            output_language=output_language,
        )
        content.color_theme = color

        forced_lang = output_language.strip().lower()
        if forced_lang and forced_lang != "auto":
            content.language = forced_lang  # type: ignore[assignment]
            if forced_lang == "fr" and content.variant == "python":
                content.variant = "ai" if role == "ai" else "it"
            elif forced_lang == "en" and content.variant == "it":
                content.variant = "ai" if role == "ai" else "python"

        target_lang = str(content.language).strip().lower() if content.language else "en"
        if not target_lang:
            target_lang = "en"
        profile_for_build = _resolve_profile_variant(
            role=role,
            output_language=target_lang,
            position_title=content.position_title,
            source_profile=profile_dict,
            use_llm_translation=False,
        )

        # 4 — Compile LaTeX
        logger.info("[Offline] [4/4] Building PDF bundle…")
        bundle: ApplicationBundle = build(
            role,
            content,
            profile=profile_for_build,
            template=template,
            job_posting=posting,
            job_url=job_url,
        )
        return bundle


def _profile_variant_path(role: str, output_language: str, position_title: str) -> Path:
    del position_title
    lang_tag = (output_language or "en").lower()
    normalized_role = role.strip().lower().replace("_", "-")
    role_label = _ROLE_LABEL_MAP.get(
        normalized_role,
        role.strip().replace("_", " ").replace("-", " ").title().replace(" ", ""),
    )
    filename = f"{CV_OWNER_SLUG}-CV_{role_label}_{lang_tag}.json"
    return GENERATED_PROFILES_DIR / filename


def _discover_legacy_variant_paths(role: str, lang: str, position_title: str) -> list[Path]:
    del position_title
    role_upper = role.upper()
    role_lower = role.lower()
    candidates: list[Path] = []

    candidates.extend(GENERATED_PROFILES_DIR.glob(f"CV_{role_upper}_*_{lang}.json"))

    legacy_dir = GENERATED_PROFILES_DIR / "generated_profiles"
    if legacy_dir.exists():
        candidates.extend(legacy_dir.glob(f"resume_profile_{role_lower}_{lang}_*.json"))

    uniq: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if path not in seen and path.is_file():
            seen.add(path)
            uniq.append(path)
    return uniq


def _resolve_profile_variant(
    role: RoleType,
    output_language: str,
    position_title: str,
    source_profile: dict,
    use_llm_translation: bool,
) -> dict:
    lang = (output_language or "en").strip().lower()
    if not lang or lang == "auto":
        lang = "en"

    title = position_title or source_profile.get("identity", {}).get("title", str(role))
    variant_path = _profile_variant_path(str(role), lang, title)
    GENERATED_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    if not variant_path.exists():
        legacy_paths = _discover_legacy_variant_paths(str(role), lang, title)
        if legacy_paths:
            latest_legacy = max(legacy_paths, key=lambda p: p.stat().st_mtime)
            try:
                latest_legacy.replace(variant_path)
                logger.info(
                    f"Migrated legacy localized profile {latest_legacy.name} -> {variant_path.name}"
                )
            except Exception as exc:
                logger.warning(
                    f"Could not migrate legacy profile {latest_legacy.name} to {variant_path.name}: {exc}"
                )

    if variant_path.exists():
        try:
            with variant_path.open(encoding="utf-8") as fh:
                cached_profile = json.load(fh)
            logger.info(f"Using cached localized profile: {variant_path.name}")
            return cached_profile
        except Exception as exc:
            logger.warning(f"Could not read cached localized profile {variant_path.name}: {exc}")

    base_profile = deepcopy(source_profile)
    if lang == "en":
        localized = base_profile
    elif lang == "fr":
        if use_llm_translation:
            try:
                localized = _translate_profile_with_llm(base_profile, target_lang=lang)
            except Exception as exc:
                logger.warning(
                    f"LLM profile translation failed for {variant_path.name}; using deterministic fallback. Error: {exc}"
                )
                localized = _localize_profile_text(base_profile, target_lang=lang)
        else:
            localized = _localize_profile_text(base_profile, target_lang=lang)
    else:
        if use_llm_translation:
            try:
                localized = _translate_profile_with_llm(base_profile, target_lang=lang)
            except Exception as exc:
                logger.warning(
                    f"LLM profile translation failed for {variant_path.name}; using source profile. Error: {exc}"
                )
                localized = base_profile
        else:
            localized = base_profile

    try:
        variant_path.write_text(
            json.dumps(localized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Localized profile saved: {variant_path}")
    except Exception as exc:
        logger.warning(f"Could not save localized profile {variant_path.name}: {exc}")
    return localized


def _translate_profile_with_llm(profile: dict, target_lang: str) -> dict:
    import importlib

    prompts_mod = importlib.import_module("langchain_core.prompts")
    parsers_mod = importlib.import_module("langchain_core.output_parsers")
    ChatPromptTemplate = getattr(prompts_mod, "ChatPromptTemplate")
    StrOutputParser = getattr(parsers_mod, "StrOutputParser")

    llm = get_llm(temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """
You translate JSON resume profiles.
Return ONLY valid JSON. Keep all keys and schema unchanged.
Translate only human-readable values to the target language.
Keep emails, phone numbers, URLs, product names, and code/library names unchanged.
Do not invent new facts.
""".strip(),
        ),
        (
            "human",
            "Translate this JSON profile to language: {target_lang}.\n\nJSON:\n{profile_json}",
        ),
    ])

    chain = prompt | llm | StrOutputParser()
    raw = chain.invoke(
        {
            "target_lang": target_lang,
            "profile_json": json.dumps(profile, ensure_ascii=False, indent=2),
        }
    )
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned.strip())
    return json.loads(cleaned)


def _tailor_offline(
    job_text: str,
    role: RoleType,
    profile_dict: dict | None = None,
    output_language: str = "auto",
) -> TailoredContent:
    """
    Simple offline content tailoring using heuristics and dictionary lookups.
    Fallback when LLM is unavailable or fails.
    """
    logger.info("Using offline dictionary-based content generation…")
    
    # Extract company name (look for common patterns)
    company_name = "Company"  # fallback
    if "company" in job_text.lower():
        lines = job_text.split("\n")
        for line in lines[:20]:
            if len(line) < 100 and any(kw in line.lower() for kw in ["company", "org", "enterprise"]):
                company_name = line.strip()
                break
    
    # Position title (look in first few lines)
    position_title = "Position"  # fallback
    lines = job_text.split("\n")
    for line in lines[:10]:
        if "engineer" in line.lower() or "developer" in line.lower() or "specialist" in line.lower():
            position_title = line.strip()
            break
    
    # Detect language from job_text (simple heuristic)
    detected_lang = "fr" if any(kw in job_text.lower() for kw in ["expérience", "compétences", "formation"]) else "en"
    
    output_lang = output_language.strip().lower()
    if output_lang in ("fr", "en"):
        detected_lang = output_lang
    
    # Simple why_this_company (fallback text)
    if detected_lang == "fr":
        why_text = "Je suis impressionné par votre entreprise et je pense que mes compétences correspondent bien à ce poste."
    else:
        why_text = "I am impressed by your company and believe my skills align well with this position."
    
    # Get top skills from profile if available
    skills = []
    if profile_dict and "skills" in profile_dict:
        skills_data = profile_dict["skills"]
        if isinstance(skills_data, dict):
            for category in skills_data.values():
                if isinstance(category, list):
                    skills.extend(category[:3])
    skills = skills[:10]
    
    # Determine variant based on language
    variant = "ai" if role == "ai" else ("it" if detected_lang == "fr" else "python")
    
    # Build content with offline data
    content = TailoredContent(
        company_name=company_name,
        position_title=position_title,
        language=detected_lang,  # type: ignore[arg-type]
        variant=variant,
        why_this_company=why_text,
        match_score=50,  # Conservative estimate
        tailored_skills=skills,
        cv_summary="",  # Will use full profile summary
        selected_experience=[],  # Will use full profile
        selected_projects=[],  # Will use full profile
    )
    
    return content


def _localize_profile_text(profile: dict, target_lang: str) -> dict:
    """
    Translate human-readable profile text to target language for preview mode.
    Keeps schema and keys unchanged; only values are localized.
    """
    if target_lang not in ("fr", "en"):
        return profile

    # Avoid extra latency/work when English is requested.
    if target_lang == "en":
        return profile

    localized = _translate_profile_dict_fr(profile)
    return localized


_FR_PHRASE_REPLACEMENTS: list[tuple[str, str]] = [
    ("(DU) in ", "(DU) en "),
    ("Diplome Universitaire (DU) in Big Data, Data Science et Analyse des Risques avec Python", "Diplome Universitaire (DU) en Big Data, Data Science et Analyse des Risques avec Python"),
    ("Cycling", "Cyclisme"),
    ("Chess", "Echecs"),
    ("AI & Automation Engineer (Network Infrastructure Background)", "Ingenieur IA & Automatisation (profil Infrastructure Reseau)"),
    ("CS Engineer (Master's, Montpellier) with a background in network infrastructure and a recent internship in AI automation.", "Ingenieur en informatique (Master, Montpellier) avec un background en infrastructure reseau et un stage recent en automatisation IA."),
    ("I build end-to-end pipelines", "Je concois des pipelines de bout en bout"),
    ("Automated an AI-driven analysis system for insurance processing", "Automatisation d'un systeme d'analyse pilote par l'IA pour le traitement d'assurance"),
    ("what took days of manual work now runs in minutes", "ce qui prenait des jours de travail manuel s'execute desormais en quelques minutes"),
    ("Excel rows", "lignes Excel"),
    ("PDF pages", "pages PDF"),
    ("and vector embeddings", "et embeddings vectoriels"),
    ("Generated 476 functional test scenarios", "Generation de 476 scenarios de tests fonctionnels"),
    ("Network monitoring tool that detects failures before users report them", "Outil de supervision reseau qui detecte les pannes avant les signalements utilisateurs"),
    ("Evolved into full-stack app:", "Evolution vers une application full-stack :"),
    ("for live finance tracking", "pour le suivi financier en temps reel"),
    ("PostGIS geolocation", "geolocalisation PostGIS"),
    ("Advanced Networks", "Reseaux avances"),
    ("Advanced Web", "Web avance"),
    ("Systems", "Systemes"),
    ("French", "Francais"),
    ("English", "Anglais"),
    ("Persian", "Persan"),
    ("Network & Systems Engineer", "Ingenieur Reseaux et Systemes"),
    ("Network Support Engineer & Automation Developer", "Ingenieur Support Reseaux et Developpeur Automatisation"),
    ("Data Analyst & Automation Developer", "Analyste Data et Developpeur Automatisation"),
    ("AI R&D & Automation Engineer", "Ingenieur R&D IA et Automatisation"),
    ("AI-Augmented Automation", "Automatisation Augmentee par l'IA"),
    ("Mobile in France", "Mobile en France"),
    ("Personal Project", "Projet Personnel"),
    ("Master's Degree", "Master"),
    ("Master in Computer Science (Bac+5)", "Master en informatique (Bac+5)"),
    ("Master's in CS at Montpellier", "Master en informatique a Montpellier"),
    ("a Master en informatique", "un Master en informatique"),
    ("Recemment diplome un Master", "Recemment diplome d'un Master"),
    ("with 7+ years", "avec 7+ annees"),
    (" at NIOC", " chez NIOC"),
    ("I leverage", "J'exploite"),
    ("Recently completed", "Recemment diplome"),
    ("University Diploma", "Diplome Universitaire"),
    ("University Diploma (DU) in Big Data, Data Science and Risk Analysis with Python", "Diplome Universitaire (DU) en Big Data, Data Science et Analyse des Risques avec Python"),
    ("Big Data, Data Science and Risk Analysis with Python", "Big Data, Data Science et Analyse des Risques avec Python"),
    ("Faculty of Economics", "Faculte d'Economie"),
    ("Faculty of Sciences", "Faculte des Sciences"),
    ("University of Montpellier, France", "Universite de Montpellier, France"),
    ("Advanced", "Avance"),
    ("Native", "Langue maternelle"),
    ("Open Source Contributions", "Contributions Open Source"),
    ("Group Mountain Hiking", "Randonnee en groupe"),
    ("Prompt Engineering", "Ingenierie de Prompt"),
    ("Technical Training", "Formation Technique"),
    ("Python and AI tools", "Python et outils d'IA"),
    ("Python et outils d'IA", "Python et des outils d'IA"),
    ("to automate infrastructure operations", "pour automatiser les operations d'infrastructure"),
    ("monitoring, reporting, and incident detection", "supervision, reporting et detection d'incidents"),
    ("built end-to-end pipelines", "concoit des pipelines de bout en bout"),
    ("combining LLMs, data engineering, and deployment", "combinant LLM, ingenierie data et deploiement"),
    ("grounded in real system-level experience", "avec une solide experience terrain systeme"),
    ("Personal AI assistant deployed on VPS", "Assistant IA personnel deploye sur VPS"),
    ("handles voice, image, finance and multilingual queries for daily use", "gere des requetes vocales, image, finance et multilingues au quotidien"),
    ("8-layer LLM fallback system", "systeme de secours LLM a 8 couches"),
    ("for resilient responses", "pour des reponses robustes"),
    ("Async data pipelines", "Pipelines de donnees asynchrones"),
    ("multimodal engine with TTS & image generation", "moteur multimodal avec TTS et generation d'image"),
    ("Developed async data pipelines for live finance tracking", "Developpement de pipelines async pour le suivi financier en temps reel"),
    ("Evolved into full-stack app with real-time web dashboard and automated Telegram alerts", "Evolution vers une application full-stack avec tableau de bord temps reel et alertes Telegram automatisees"),
    ("detects failures before user reports", "detecte les pannes avant les signalements utilisateurs"),
    ("deployed on 70 Cisco switches", "deploye sur 70 switchs Cisco"),
    ("real-time web dashboard", "tableau de bord web en temps reel"),
    ("automated Telegram alerts", "alertes Telegram automatisees"),
    ("Managed network and VoIP infrastructure", "Gestion d'une infrastructure reseau et VoIP"),
    ("incident resolution", "resolution d'incidents"),
    ("SLA compliance", "respect des SLA"),
    ("24/7 on-call", "astreinte 24/7"),
    ("Built Python/SNMP automation scripts", "Conception de scripts d'automatisation Python/SNMP"),
    ("to manage 70 Cisco 2960 switches remotely", "pour gerer a distance 70 switchs Cisco 2960"),
    ("eliminating 70% of on-site interventions", "reduisant de 70% les interventions sur site"),
    ("Deployed SolarWinds dashboards for proactive monitoring", "Deploiement de tableaux de bord SolarWinds pour une supervision proactive"),
    ("detected 30% of incidents before user reports", "detection de 30% des incidents avant signalement utilisateur"),
    ("Wrote Bash scripts reducing diagnostic time", "Ecriture de scripts Bash reduisant le temps de diagnostic"),
    ("automated reporting pipelines via Python", "automatisation des pipelines de reporting via Python"),
    ("Built AI-powered data extraction pipelines", "Mise en place de pipelines d'extraction de donnees basees sur l'IA"),
    ("using LLMs and vector embeddings", "avec LLM et embeddings vectoriels"),
    ("Generated 476 automated test scenarios", "Generation de 476 scenarios de test automatises"),
    ("Generated 476 automated test scenarios, reducing manual QA effort by 40%;", "Generation de 476 scenarios de test automatises, reduisant l'effort QA manuel de 40%;"),
    ("via Multi-Agent CrewAI framework", "via un framework multi-agent CrewAI"),
    ("freeing the QA team from repetitive work", "en liberant l'equipe QA des taches repetitives"),
    ("for 1,500+ users", "pour 1 500+ utilisateurs"),
    ("by 40%", "de 40%"),
    ("reducing manual QA effort", "reduisant l'effort QA manuel"),
    ("Internship", "Stage"),
    ("Internal", "Interne"),
]

_FR_REGEX_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\\bNetwork Support Engineer\\b", "Ingenieur Support Reseaux"),
    (r"\\bData Analyst\\b", "Analyste Data"),
    (r"\\bAutomation Developer\\b", "Developpeur Automatisation"),
    (r"\\breal-time\\b", "temps reel"),
    (r"\\bmonitoring\\b", "supervision"),
    (r"\\breporting\\b", "reporting"),
    (r"\\bincident detection\\b", "detection d'incidents"),
]


def _translate_profile_dict_fr(value):
    if isinstance(value, dict):
        return {k: _translate_profile_dict_fr(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_translate_profile_dict_fr(v) for v in value]
    if isinstance(value, str):
        return _translate_text_fr(value)
    return value


def _translate_text_fr(text: str) -> str:
    out = text
    for src, dst in _FR_PHRASE_REPLACEMENTS:
        out = out.replace(src, dst)
    for pattern, repl in _FR_REGEX_REPLACEMENTS:
        out = re.sub(pattern, repl, out)
    return out
