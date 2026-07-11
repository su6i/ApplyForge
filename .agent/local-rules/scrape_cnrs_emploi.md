# Skill: Scrape emploi.cnrs.fr

## Summary

The CNRS job-posting portal is at `emploi.cnrs.fr`. Results are loaded with JavaScript —
they are only accessible via **Playwright**.

---

## URL structure

```
# search page
https://emploi.cnrs.fr/Offres/Recherche.aspx

# a single posting's detail
https://emploi.cnrs.fr/Offres/CDD/<REF>/Default.aspx
https://emploi.cnrs.fr/Offres/PASS/<REF>/Default.aspx   # apprentissage
https://emploi.cnrs.fr/Offres/Doctorant/<REF>/Default.aspx
```

---

## Keyword search code

```python
from playwright.sync_api import sync_playwright

def scrape_cnrs_jobs(keywords: list[str]) -> list[dict]:
    """
    Search CNRS postings by keyword.
    Returns: list of {title, url}
    """
    results = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for kw in keywords:
            pg = browser.new_page()
            pg.goto('https://emploi.cnrs.fr/Offres/Recherche.aspx',
                    wait_until='networkidle', timeout=30000)
            pg.wait_for_timeout(1500)

            # fill the search field with the correct ID
            pg.fill('#InputSearchBy', kw)
            pg.wait_for_timeout(300)
            pg.keyboard.press('Enter')
            pg.wait_for_timeout(3000)

            links = pg.query_selector_all('a[href*="/Offres/"][href*="Default.aspx"]')
            for l in links:
                href = l.get_attribute('href') or ''
                text = l.text_content().strip()
                if text and len(text) > 10:
                    full_url = 'https://emploi.cnrs.fr' + href if href.startswith('/') else href
                    if full_url not in seen:
                        seen.add(full_url)
                        results.append({'title': text[:80], 'url': full_url})

            pg.close()

        browser.close()

    return results
```

---

## Suggested keywords for an IT / network profile

```python
IT_KEYWORDS = ['informatique', 'réseau', 'système', 'développeur', 'python',
               'administrateur système', 'linux', 'devops', 'logiciel']
```

---

## Filtering out unrelated postings

```python
# drop bioinformatique, doctorant, apprentissage, chercheur
SKIP_TITLES = ['bioinformatique', 'doctorant', 'postdoc', 'postdoctoral',
               'apprenti', 'chercheur', 'doctorale', 'thèse', 'chimie',
               'biologie', 'physique', 'écologie']

SKIP_PATHS = ['/Offres/Doctorant/', '/Offres/PASS/']

def filter_it_jobs(jobs: list[dict]) -> list[dict]:
    return [
        j for j in jobs
        if not any(kw in j['title'].lower() for kw in SKIP_TITLES)
        and not any(p in j['url'] for p in SKIP_PATHS)
    ]
```

---

## Eligibility criteria — check before generating a CV

Before any application, read `eligibility_screening.md` and extract every blocking
criterion from the job text.

---

## Notes

1. **Input field ID:** `#InputSearchBy` — the main search text field.
2. **URL filters do not work** — GET parameters such as `?brancheActivite=BAI` are ignored.
3. **Submit:** send with `pg.keyboard.press('Enter')` — the Submit button is sometimes hidden.
4. **Apprentissage/PASS:** the `/Offres/PASS/` path = apprenticeship contracts → usually irrelevant.
5. **Apply link:** each posting has a "Postuler sur le site employeur" button or an internal form.
6. **Availability check:** `"L'offre demandée n'est plus disponible"` = the posting is closed.

---

## How to apply on CNRS

- Usually via an online form inside emploi.cnrs.fr.
- Requires creating an account on the portal.
- After login → "Postuler" → upload CV + cover letter.
