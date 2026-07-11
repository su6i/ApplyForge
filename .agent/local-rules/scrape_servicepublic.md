# Skill: Scrape choisirleservicepublic.gouv.fr

## Summary

`choisirleservicepublic.gouv.fr` is the official French public-sector job-posting portal.
Results are loaded with JavaScript — they are only accessible via **Playwright**.

---

## URL structure

```
# all postings
https://choisirleservicepublic.gouv.fr/nos-offres/

# domain filter (Numérique = 3522)
https://choisirleservicepublic.gouv.fr/nos-offres/filtres/domaine/3522/

# pagination
https://choisirleservicepublic.gouv.fr/nos-offres/filtres/domaine/3522/page/2/

# a single posting's detail
https://choisirleservicepublic.gouv.fr/offre-emploi/[slug]-reference-[ref]/
```

### Key domains
| ID | Domain |
|---|---|
| 3522 | Numérique (IT/Digital) |
| 3503 | Achats |
| 3511 | Défense |

---

## Listing-extraction code

```python
from playwright.sync_api import sync_playwright
import re

def scrape_servicepublic_listings(domain_id=3522, max_pages=5):
    """
    Extract job listings from choisirleservicepublic.gouv.fr
    Returns: list of {title, location, employer, url}
    """
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for page_num in range(1, max_pages + 1):
            if page_num == 1:
                url = f'https://choisirleservicepublic.gouv.fr/nos-offres/filtres/domaine/{domain_id}/'
            else:
                url = f'https://choisirleservicepublic.gouv.fr/nos-offres/filtres/domaine/{domain_id}/page/{page_num}/'

            pg = browser.new_page()
            pg.goto(url, wait_until='networkidle', timeout=30000)
            pg.wait_for_timeout(3000)

            # extract links and titles
            links = pg.query_selector_all('a[href*="offre-emploi"]')
            for l in links:
                title = l.text_content().strip()
                href = l.get_attribute('href') or ''
                if title and href and 'offre-emploi' in href:
                    results.append({'title': title, 'url': href, 'location': '', 'employer': ''})

            # extract location/employer from the page text
            body_lines = [ln.strip() for ln in pg.inner_text('body').split('\n') if ln.strip()]
            i = 0
            while i < len(body_lines):
                line = body_lines[i]
                if i + 1 < len(body_lines) and body_lines[i+1] == 'Numérique':
                    location = ''
                    employer = ''
                    for j in range(i+2, min(i+15, len(body_lines))):
                        if j > 0 and body_lines[j-1] == 'Localisation :':
                            location = body_lines[j]
                        if j > 0 and body_lines[j-1] == 'Employeur :':
                            employer = body_lines[j]
                    # update the last item added
                    for r in reversed(results):
                        if r['title'] == line:
                            r['location'] = location
                            r['employer'] = employer
                            break
                i += 1

            pg.close()

        browser.close()

    # de-duplicate
    seen = set()
    unique = []
    for r in results:
        key = r['title'] + r['url']
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique
```

---

## Single-posting detail-extraction code

```python
def scrape_servicepublic_job(url: str) -> dict:
    """
    Extract the full detail of a single posting.
    Returns: {experience, category, contract, missions, profile}
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page()
        pg.goto(url, wait_until='networkidle', timeout=30000)
        pg.wait_for_timeout(2000)
        body = pg.inner_text('body')
        pg.close()
        browser.close()

    lines = [l.strip() for l in body.split('\n') if l.strip()]
    info = {}
    FIELDS = ['expérience souhaitée', 'catégorie', 'nature du contrat',
              'vos missions', 'profil recherché', 'niveau d\'études']

    for i, line in enumerate(lines):
        ll = line.lower()
        for f in FIELDS:
            if f in ll:
                val = lines[i+1] if i+1 < len(lines) else ''
                info[f] = val
                break

    return info
```

---

## Eligibility criteria — check before generating a CV

Before any application, read `eligibility_screening.md` and extract every blocking
criterion from the job text.

---

## Notes

1. **JavaScript-rendered**: no simple scraper (requests, curl) works — Playwright only.
2. **Filters are interactive**: clicking filters in Playwright needs `wait_until='networkidle'`.
3. **Nationality**: Police/Gendarmerie/XPN posts usually require French nationality.
4. **Categories**:
   - Cat. A = cadre (management, usually Bac+5)
   - Cat. B = intermediate profession (technician)
   - Cat. C = base-level employee
5. **"Confirmé"** = prior experience mandatory — not suitable for a junior profile.
6. **"Non renseigné"** = unspecified, may be junior-friendly.
7. **Playwright install**: `uv run playwright install chromium`

---

## Suggested search for a junior IT profile

```python
# filter: Numérique + search titles for junior-friendly roles
JUNIOR_TITLES = ['technicien', 'assistant', 'chargé', 'développeur', 'administrateur']
SENIOR_TITLES = ['responsable', 'chef', 'directeur', 'expert', 'lead', 'adjoint']

jobs = scrape_servicepublic_listings(domain_id=3522, max_pages=10)
junior_jobs = [
    j for j in jobs
    if any(t in j['title'].lower() for t in JUNIOR_TITLES)
    and not any(t in j['title'].lower() for t in SENIOR_TITLES)
]
```
