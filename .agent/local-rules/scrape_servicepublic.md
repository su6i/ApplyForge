# Skill: Scrape choisirleservicepublic.gouv.fr

## خلاصه

سایت `choisirleservicepublic.gouv.fr` پورتال رسمی آگهی‌های شغلی بخش عمومی فرانسه است.
نتایج با JavaScript بارگذاری می‌شوند — فقط با **Playwright** قابل دسترسی است.

---

## ساختار URL

```
# همه آگهی‌ها
https://choisirleservicepublic.gouv.fr/nos-offres/

# فیلتر دامنه (Numérique = 3522)
https://choisirleservicepublic.gouv.fr/nos-offres/filtres/domaine/3522/

# صفحه‌بندی
https://choisirleservicepublic.gouv.fr/nos-offres/filtres/domaine/3522/page/2/

# جزئیات یک آگهی
https://choisirleservicepublic.gouv.fr/offre-emploi/[slug]-reference-[ref]/
```

### دامنه‌های مهم
| ID | دامنه |
|---|---|
| 3522 | Numérique (IT/Digital) |
| 3503 | Achats |
| 3511 | Défense |

---

## کد استخراج لیست آگهی‌ها

```python
from playwright.sync_api import sync_playwright
import re

def scrape_servicepublic_listings(domain_id=3522, max_pages=5):
    """
    استخراج لیست آگهی‌های شغلی از choisirleservicepublic.gouv.fr
    برمی‌گرداند: list of {title, location, employer, url}
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

            # استخراج لینک‌ها و عناوین
            links = pg.query_selector_all('a[href*="offre-emploi"]')
            for l in links:
                title = l.text_content().strip()
                href = l.get_attribute('href') or ''
                if title and href and 'offre-emploi' in href:
                    results.append({'title': title, 'url': href, 'location': '', 'employer': ''})

            # استخراج location/employer از متن صفحه
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
                    # به‌روزرسانی آخرین آیتم اضافه‌شده
                    for r in reversed(results):
                        if r['title'] == line:
                            r['location'] = location
                            r['employer'] = employer
                            break
                i += 1

            pg.close()

        browser.close()

    # حذف تکراری‌ها
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

## کد استخراج جزئیات یک آگهی

```python
def scrape_servicepublic_job(url: str) -> dict:
    """
    استخراج جزئیات کامل یک آگهی شغلی
    برمی‌گرداند: {experience, category, contract, missions, profile}
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

## معیارهای حذفی — قبل از تولید CV بررسی کن

قبل از هر candidature، فایل `eligibility_screening.md` را بخوان و تمام معیارهای بلاک‌کننده را از متن آگهی استخراج کن.

---

## نکات مهم

1. **JavaScript-rendered**: هیچ scraper ساده‌ای (requests, curl) کار نمی‌کند — فقط Playwright
2. **فیلترها interactive هستند**: کلیک روی فیلترها در Playwright نیاز به `wait_until='networkidle'` دارد
3. **ملیت**: پست‌های Police/Gendarmerie/XPN معمولاً نیاز به ملیت فرانسوی دارند
4. **دسته‌بندی**:
   - Cat. A = cadre (مدیریتی، معمولاً Bac+5)
   - Cat. B = profession intermédiaire (تکنیسین)
   - Cat. C = employé (پایه)
5. **"Confirmé"** = تجربه قبلی الزامی — برای پروفایل junior مناسب نیست
6. **"Non renseigné"** = نامشخص، می‌تواند junior-friendly باشد
7. **Playwright install**: `uv run playwright install chromium`

---

## جستجوی پیشنهادی برای پروفایل IT junior

```python
# فیلتر: Numérique + جستجو در title برای عناوین junior-friendly
JUNIOR_TITLES = ['technicien', 'assistant', 'chargé', 'développeur', 'administrateur']
SENIOR_TITLES = ['responsable', 'chef', 'directeur', 'expert', 'lead', 'adjoint']

jobs = scrape_servicepublic_listings(domain_id=3522, max_pages=10)
junior_jobs = [
    j for j in jobs
    if any(t in j['title'].lower() for t in JUNIOR_TITLES)
    and not any(t in j['title'].lower() for t in SENIOR_TITLES)
]
```
