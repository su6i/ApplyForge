"""
job_scraper.py — Fetch a job posting URL and return the raw text content.

Strategy:
  1. Try plain requests + BeautifulSoup (fast, no browser needed).
  2. If the page looks JS-rendered (body too short), fall back to Selenium.

Returns a JobPosting dataclass with url, title (best-effort), and body text.
"""
from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.core.logger import logger


class JobScrapeError(Exception):
    """Raised when a job posting cannot be turned into usable text — abort before any LLM call."""


# Minimum meaningful character count before we suspect the page is JS-rendered.
_MIN_BODY_LENGTH = 300

# Minimum extracted-text length before we trust a PDF was parsed correctly.
_MIN_PDF_TEXT_LENGTH = 30

# Tags whose text is never useful (navigation, scripts, styles, …)
_NOISE_TAGS = {"script", "style", "noscript", "header", "footer", "nav", "aside"}

# Keywords that identify direct application links ("postuler", "apply", …)
_APPLY_LINK_SIGNALS = {"postuler", "postulez", "je postule", "apply", "candidater", "candidature", "s'inscrire"}


@dataclass
class JobPosting:
    url: str
    title: str = ""
    body: str = ""
    raw_html: str = field(default="", repr=False)
    apply_url: str = ""  # direct application link extracted from page (postuler/apply)


def scrape(url: str, headless: bool = True) -> JobPosting:
    """
    Main entry point.

    Parameters
    ----------
    url      : Full job posting URL.
    headless : If browser fallback is triggered, run headlessly.

    Returns
    -------
    JobPosting with .body populated.
    """
    logger.info(f"Scraping job URL: {url}")

    posting = _scrape_with_requests(url)
    if len(posting.body) < _MIN_BODY_LENGTH:
        logger.warning(
            f"requests body too short ({len(posting.body)} chars), trying Playwright fallback…"
        )
        posting = _scrape_with_playwright(url, headless=headless)

    if len(posting.body) < _MIN_BODY_LENGTH:
        logger.warning(
            f"Playwright body too short ({len(posting.body)} chars), trying Selenium fallback…"
        )
        posting = _scrape_with_selenium(url, headless=headless)

    logger.info(f"Scraped {len(posting.body)} chars from {url!r}")
    return posting


# ─── requests + BeautifulSoup ─────────────────────────────────────────────────

def _scrape_with_requests(url: str) -> JobPosting:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        logger.error(f"requests failed for {url}: {exc}")
        return JobPosting(url=url)

    if _looks_like_pdf(resp):
        return _parse_pdf(url, resp.content)

    return _parse_html(url, resp.text)


# ─── PDF parsing ───────────────────────────────────────────────────────────────

def _looks_like_pdf(resp: requests.Response) -> bool:
    """Detect a PDF response by Content-Type header or magic bytes (%PDF-)."""
    content_type = resp.headers.get("Content-Type", "").lower()
    if "application/pdf" in content_type:
        return True
    return resp.content[:5] == b"%PDF-"


def _parse_pdf(url: str, content: bytes) -> JobPosting:
    """Extract text from a PDF job posting via pdfminer.six.

    Raises JobScrapeError if extraction fails or yields no usable text —
    the caller must abort before any LLM call rather than proceed with garbage.
    """
    try:
        from pdfminer.high_level import extract_text as _pdf_extract
    except ImportError as exc:
        raise JobScrapeError(
            "pdfminer.six is required for PDF job postings: uv add pdfminer-six"
        ) from exc

    try:
        text = _pdf_extract(io.BytesIO(content)) or ""
    except Exception as exc:
        raise JobScrapeError(f"Could not extract text from PDF job posting {url!r}: {exc}") from exc

    body = _clean_text(text)
    if len(body) < _MIN_PDF_TEXT_LENGTH:
        raise JobScrapeError(
            f"PDF job posting {url!r} yielded no usable text ({len(body)} chars) — aborting."
        )

    title = next((line.strip() for line in body.splitlines() if line.strip()), "")
    logger.info(f"Extracted {len(body)} chars from PDF job posting: {url!r}")
    return JobPosting(url=url, title=title, body=body)


# ─── Playwright fallback ──────────────────────────────────────────────────────

def _scrape_with_playwright(url: str, headless: bool = True) -> JobPosting:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed; skipping.")
        return JobPosting(url=url)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            )
            page.goto(url, wait_until="networkidle", timeout=30_000)
            _dismiss_cookie_banners(page)
            _remove_noise_elements(page)
            html = page.content()
            browser.close()
        return _parse_html(url, html)
    except Exception as exc:
        logger.error(f"Playwright scrape failed for {url}: {exc}")
        return JobPosting(url=url)


# ─── Cookie banner dismissal ──────────────────────────────────────────────────

def _remove_noise_elements(page) -> None:
    """Remove cookie banners, modals and nav noise from the DOM before extraction."""
    page.evaluate("""
        const noiseSelectors = [
            // Axeptio (WTTJ, many French sites)
            '#axeptio_overlay', '#axeptio-widget', '[id^="axeptio"]',
            // Didomi
            '#didomi-popup', '#didomi-host',
            // OneTrust
            '#onetrust-banner-sdk', '#onetrust-consent-sdk',
            // Generic overlays
            '[class*="cookie"]', '[id*="cookie"]',
            '[class*="consent"]', '[id*="consent"]',
            '[class*="gdpr"]', '[id*="gdpr"]',
            // Navigation noise
            'header', 'footer', 'nav',
        ];
        noiseSelectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => el.remove());
        });
    """)


def _dismiss_cookie_banners(page) -> None:
    """Click common cookie accept buttons so they don't pollute extracted text."""
    selectors = [
        # Axeptio (used by WTTJ and many French sites)
        "#axeptio_btn_acceptAll",
        "#didomi-notice-agree-button",
        "#onetrust-accept-btn-handler",
        # Generic
        "button[id*='acceptAll']",
        "button[id*='accept-all']",
        # French RGPD text
        "button:has-text('OK pour moi')",
        "button:has-text('Tout accepter')",
        "button:has-text('Accepter tout')",
        "button:has-text('Accept all')",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            btn.click(timeout=3_000)
            # Wait for the banner container to disappear
            page.locator("#axeptio_overlay, .axeptio-widget, [class*='cookie']").first.wait_for(
                state="hidden", timeout=3_000
            )
            logger.debug(f"Cookie banner dismissed via: {sel}")
            return
        except Exception:
            continue


# ─── Selenium fallback ────────────────────────────────────────────────────────

def _scrape_with_selenium(url: str, headless: bool = True) -> JobPosting:
    try:
        from src.core.browser import init_browser  # lazy import — Selenium optional
    except ImportError:
        logger.error("Selenium not installed; cannot use browser fallback.")
        return JobPosting(url=url)

    driver = None
    try:
        driver = init_browser(headless=headless)
        driver.get(url)
        time.sleep(3)  # wait for JS render
        html = driver.page_source
        return _parse_html(url, html)
    except Exception as exc:
        logger.error(f"Selenium scrape failed for {url}: {exc}")
        return JobPosting(url=url)
    finally:
        if driver:
            driver.quit()


# ─── HTML parsing ─────────────────────────────────────────────────────────────

def _parse_html(url: str, html: str) -> JobPosting:
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise tags in-place
    for tag in soup(list(_NOISE_TAGS)):
        tag.decompose()

    # Best-effort title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(separator=" ", strip=True)

    # Body text: join all visible text, strip trailing "related offers"/help
    # noise, collapse whitespace
    raw_text = soup.get_text(separator="\n", strip=True)
    raw_text = _strip_trailing_noise(raw_text)
    body = _clean_text(raw_text)
    apply_url = _extract_apply_url(url, soup)

    return JobPosting(url=url, title=title, body=body, raw_html=html, apply_url=apply_url)


def _extract_apply_url(base_url: str, soup: BeautifulSoup) -> str:
    """Return the first direct application link found on the page, or empty string."""
    from urllib.parse import urljoin, urlparse
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        text = a.get_text(strip=True).lower()
        href_lower = href.lower()
        if any(sig in text for sig in _APPLY_LINK_SIGNALS) or any(sig in href_lower for sig in _APPLY_LINK_SIGNALS):
            if href.startswith("http"):
                return href
            parsed = urlparse(base_url)
            return urljoin(f"{parsed.scheme}://{parsed.netloc}", href)
    return ""


def _clean_text(text: str) -> str:
    # Collapse sequences of blank lines to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse horizontal whitespace
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# Boilerplate markers where job boards start listing unrelated "similar/related
# offers" or generic site help text — never part of the actual posting. Left
# in, this noise can (a) inflate token cost / dilute the LLM's tailoring
# context, and (b) spuriously trigger keyword-based heuristics downstream —
# e.g. a France Travail "D'autres offres..." sidebar once contained an
# unrelated "Technicien" job title, which falsely triggered
# technicien_adapter.is_technicien_tier() on an unrelated Cadre-tier posting.
_TRAILING_NOISE_MARKERS: tuple[str, ...] = (
    "D'autres offres peuvent vous intéresser",  # France Travail
    "Offres similaires",                          # generic FR job boards
    "Vous pourriez également être intéressé",     # generic FR job boards
)


def _strip_trailing_noise(text: str) -> str:
    """Cut the body at the first known 'related offers'/help-boilerplate
    marker, if present. These markers reliably sit after the real posting
    content, so truncating there is safe."""
    cut_at = len(text)
    for marker in _TRAILING_NOISE_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            cut_at = min(cut_at, idx)
    return text[:cut_at].rstrip()
