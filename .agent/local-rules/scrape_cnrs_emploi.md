# Skill: Scrape emploi.cnrs.fr

## خلاصه

پورتال آگهی‌های شغلی CNRS در `emploi.cnrs.fr`. نتایج با JavaScript بارگذاری می‌شوند — فقط با **Playwright** قابل دسترسی است.

---

## ساختار URL

```
# صفحه جستجو
https://emploi.cnrs.fr/Offres/Recherche.aspx

# جزئیات یک آگهی
https://emploi.cnrs.fr/Offres/CDD/<REF>/Default.aspx
https://emploi.cnrs.fr/Offres/PASS/<REF>/Default.aspx   # apprentissage
https://emploi.cnrs.fr/Offres/Doctorant/<REF>/Default.aspx
```

---

## کد جستجو با keyword

```python
from playwright.sync_api import sync_playwright

def scrape_cnrs_jobs(keywords: list[str]) -> list[dict]:
    """
    جستجوی آگهی‌های CNRS با کلمات کلیدی.
    برمی‌گرداند: list of {title, url}
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

            # پر کردن فیلد جستجو با ID صحیح
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

## کلمات کلیدی پیشنهادی برای پروفایل IT/réseau

```python
IT_KEYWORDS = ['informatique', 'réseau', 'système', 'développeur', 'python',
               'administrateur système', 'linux', 'devops', 'logiciel']
```

---

## فیلتر آگهی‌های نامرتبط

```python
# حذف bioinformatique، doctorant، apprentissage، chercheur
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

## نکات مهم

1. **Input field ID:** `#InputSearchBy` — فیلد متنی اصلی جستجو
2. **فیلترهای URL کار نمی‌کنند** — پارامترهای GET مثل `?brancheActivite=BAI` نادیده گرفته می‌شوند
3. **Submit:** با `pg.keyboard.press('Enter')` ارسال کن — دکمه Submit گاهی hidden است
4. **Apprentissage/PASS:** مسیر `/Offres/PASS/` = قراردادهای apprentissage → معمولاً نامرتبط
5. **Apply link:** هر آگهی یک دکمه "Postuler sur le site employeur" یا فرم داخلی دارد
6. **Availability check:** `"L'offre demandée n'est plus disponible"` = آگهی بسته شده

---

## روش apply در CNRS

- معمولاً از طریق فرم آنلاین داخل سایت emploi.cnrs.fr
- نیاز به ایجاد حساب کاربری در پورتال
- بعد از login → "Postuler" → آپلود CV + lettre de motivation
