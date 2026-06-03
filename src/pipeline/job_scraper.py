"""
job_scraper.py — Fetch a job posting URL and return the raw text content.

Strategy:
  1. Try plain requests + BeautifulSoup (fast, no browser needed).
  2. If the page looks JS-rendered (body too short), fall back to Selenium.

Returns a JobPosting dataclass with url, title (best-effort), and body text.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.core.logger import logger


# Minimum meaningful character count before we suspect the page is JS-rendered.
_MIN_BODY_LENGTH = 300

# Tags whose text is never useful (navigation, scripts, styles, …)
_NOISE_TAGS = {"script", "style", "noscript", "header", "footer", "nav", "aside"}


@dataclass
class JobPosting:
    url: str
    title: str = ""
    body: str = ""
    raw_html: str = field(default="", repr=False)


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

    return _parse_html(url, resp.text)


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

    # Body text: join all visible text, collapse whitespace
    raw_text = soup.get_text(separator="\n", strip=True)
    body = _clean_text(raw_text)

    return JobPosting(url=url, title=title, body=body, raw_html=html)


def _clean_text(text: str) -> str:
    # Collapse sequences of blank lines to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse horizontal whitespace
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
