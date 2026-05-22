# CV — CLAUDE.md

## این پروژه چیه

سیستم شخصی تولید رزومه و درخواست شغلی + pipeline انتشار محتوای تحلیلی روی LinkedIn.
دو کارکرد اصلی:
1. **CV Generator** — از یک URL آگهی شغلی، رزومه و کاور لتر شخصی‌سازی‌شده تولید می‌کند
2. **LinkedIn Content** — carousel PDF تحلیلی می‌سازد و با API رسمی LinkedIn منتشر می‌کند

---

## قانون امنیتی: بررسی اجباری قبل از هر کامیت

**قبل از هر `git commit`، با دقت و وسواس بررسی کن که هیچ‌کدام از موارد زیر در staged files وجود ندارد:**

| چه چیزی | نمونه |
|---|---|
| نام و نام خانوادگی واقعی | Firstname Lastname، هر اسم شخصی |
| آدرس ایمیل | user@example.com، هر ایمیل دیگر |
| شماره تلفن | +XX X XX XX XX XX، هر شماره‌ای |
| آدرس فیزیکی | شهر، کدپستی، آدرس |
| token و API key | هر رشته‌ای که شبیه secret باشد |
| اطلاعات کارفرما یا شرکت‌ها | نام شرکت‌های درخواست‌شده، نام مدیران |
| محتوای فایل‌های gitignored | `master_cv.json`، `Applied/`، `.env`، `data/` |

**روش بررسی:**
```bash
git diff --cached          # همه staged changes را بخوان
git diff --cached --stat   # لیست فایل‌های staged
```

اگر حتی یک مورد مشکوک دیدی → `git restore --staged <file>` و از کاربر بپرس.
در صورت شک، کامیت نکن.

---

## قانون طلایی: مستندسازی اتوماتیک

**بعد از هر تغییر در کد، دستورات، یا ساختار پروژه:**

1. `README.md` — اگر دستور جدیدی اضافه شد، روش استفاده آن را بنویس
2. `docs/` — اگر workflow یا gitignore policy تغییر کرد، فایل مرتبط را به‌روز کن
3. این فایل (`CLAUDE.md`) — اگر فایل کلیدی یا تصمیم مهمی تغییر کرد، ثبت کن
4. حتی یک جمله کوتاه بهتر از سکوت است — آینده نگر باش، نه فقط حل‌کننده مشکل فعلی

اگر ابزار AI این پروژه را باز می‌کند، باید بتواند فقط با خواندن همین فایل شروع به کار کند.

---

## فایل‌های کلیدی

### CV Generator

| فایل | نقش |
|---|---|
| `main.py` | Entry point — `uv run main.py apply URL` |
| `src/pipeline/service.py` | `ApplicationService`: orchestrator اصلی pipeline |
| `src/pipeline/latex_builder.py` | کامپایل LaTeX، `_SPONTANEOUS_MAP`، `build_spontaneous()` |
| `src/core/location_utils.py` | تشخیص منطقه اکسیتانی → Montpellier/Grenoble |
| `templates/altacv/` | قالب‌های AltaCV (xelatex) |
| `templates/lato/` | قالب‌های Lato/article (pdflatex) |
| `templates/classic/` | قالب‌های ModernCV banking (pdflatex) |
| `templates/tina/` | قالب‌های Tina (pdflatex) |
| `templates/shared/` | `personal_data.tex` — **private، گیت‌ایگنور** |
| `cover_letters/` | قالب‌های LaTeX کاور لتر |
| `master_cv.json` | پروفایل شخصی — **private، گیت‌ایگنور** |
| `master_cv.example.json` | نمونه anonymized — safe to commit |

### LinkedIn Content

| فایل | نقش |
|---|---|
| `scripts/linkedin_post.py` | ارسال PDF carousel به LinkedIn |
| `scripts/data_jobs_scraper.mjs` | اسکرپ آمار France Travail MétierScope |
| `docs/it_rome_codes.json` | کدهای ROME برای مشاغل IT/Data |
| `docs/data_jobs_stats.json` | داده خام scraper (gitignored) |
| `linkedin/02_data_science/carousel.md` | منبع Markdown کاروسل data science |
| `linkedin/idees_posts.md` | ایده‌های پست بعدی — **private، گیت‌ایگنور** |

### مستندات

| فایل | نقش |
|---|---|
| `README.md` | راهنمای کامل برای کاربر و AI |
| `docs/architecture.md` | معماری pipeline |
| `docs/git-workflow.md` | قوانین git و فایل‌های tracked/ignored |
| `docs/bot-setup.md` | راه‌اندازی Telegram bot |
| `docs/latex-templates.md` | ساختار قالب‌های LaTeX |

---

## دستورات مهم

### ساخت رزومه

```bash
# تولید رزومه + کاور لتر از URL شغلی (با LLM)
uv run main.py apply https://company.com/jobs/12345

# candidature spontanée — بدون LLM، از قالب آماده
uv run main.py spontaneous ai                        # AI MLOps فرانسوی
uv run main.py spontaneous ai-en                     # AI MLOps انگلیسی
uv run main.py spontaneous devops-alternance         # DevOps Alternance
uv run main.py spontaneous phd                       # PhD academic
uv run main.py spontaneous polyvalent                # Polyvalent
uv run main.py spontaneous ai --city montpellier     # با شهر مشخص (Occitanie → Montpellier)
# نقش‌های موجود: ai, ai-en, mlops, mlops-en, devops, devops-alternance, phd, polyvalent
```

### LinkedIn Carousel

```bash
# ساخت PDF carousel (نیاز به amir-cli)
amir pdf --theme carousel linkedin/02_data_science/carousel.md \
         -o linkedin/02_data_science/carousel.pdf

# Auth (یک‌بار)
python scripts/linkedin_post.py --auth

# پیش‌نمایش بدون ارسال
python scripts/linkedin_post.py --post linkedin/02_data_science --dry-run

# ارسال واقعی
python scripts/linkedin_post.py --post linkedin/02_data_science
```

### اسکرپ داده France Travail

```bash
node scripts/data_jobs_scraper.mjs
# خروجی: docs/data_jobs_stats.json
```

---

## قوانین LinkedIn

- **حداکثر ۲ پست در هفته**، حداقل **۳ روز** فاصله بین پست‌های carousel
- بهترین روزها: دوشنبه/سه‌شنبه یا چهارشنبه
- از پنج‌شنبه عصر تا یکشنبه پرهیز کن
- **قبل از هر ارسال**: تاریخ آخرین پست را از API بخوان و نمایش بده
- هرگز بدون تأیید صریح کاربر ارسال نکن اگر کمتر از ۳ روز گذشته باشد

```python
# چک تاریخ آخرین پست
headers = {"Authorization": f"Bearer {token}", "LinkedIn-Version": "202604",
           "X-Restli-Protocol-Version": "2.0.0"}
r = requests.get(f"https://api.linkedin.com/rest/posts?author={owner_urn}&q=author&count=5&sortBy=LAST_MODIFIED", headers=headers)
ts = r.json()["elements"][0].get("publishedAt")
last = datetime.fromtimestamp(ts/1000, tz=timezone.utc)
```

**LinkedIn-Version فعلی:** `202604` — اگر خطای `426 NONEXISTENT_VERSION` دیدی به‌روز کن.

---

## فایل‌های Private (گیت‌ایگنور)

| فایل/پوشه | دلیل |
|---|---|
| `master_cv.json` | اطلاعات شخصی واقعی |
| `Applied/` | درخواست‌های شغلی — نام‌ها، رد شدن‌ها |
| `data/` | داده‌های cache و پروفایل |
| `linkedin/idees_posts.md` | استراتژی محتوای خصوصی |
| `.env` | کلیدهای API |
| `.linkedin_token.json` | OAuth token — با `--auth` بازسازی کن |

---

## Setup برای اولین بار

```bash
# ۱. کپی فایل‌های نمونه
cp master_cv.example.json master_cv.json   # پروفایل خودت را پر کن
cp .env.example .env                       # کلیدهای API را وارد کن
# در .env حتماً تنظیم کن:
#   CV_OWNER_SLUG=Firstname_LASTNAME   ← پیشوند نام فایل‌های خروجی PDF

# ۲. نصب وابستگی‌ها
pip install -r requirements.txt

# ۳. برای LinkedIn (اختیاری)
python scripts/linkedin_post.py --auth
```

---

## قوانین قالب LaTeX

- **هاردکد ممنوع** — هر فایل `.tex` tracked باید از ماکروها استفاده کند
- **ماکروهای استاندارد:** `\cvname`، `\cvemail`، `\cvphone`، `\cvlocation`، `\cvgithub`، `\cvlinkedin`
- **ModernCV (classic):** اضافه `\cvfirstname` و `\cvlastname` برای `\name{}{}`
- **PhD academic (lato):** اضافه `\cvorcid` و `\cvauthorcitation`
- **الگوی پرامبل:**
  ```latex
  \providecommand{\cvname}{Firstname LASTNAME}
  ...
  \input{../shared/personal_data}   % override کننده
  ```
- **naming:** قالب‌ها → `CV_{Role}_{lang}.tex` (بدون اسم شخصی)
- **فایل نهایی** → `Applied/` (گیت‌ایگنور، اسم شخصی در نام فایل مجاز است)

## منطق انتخاب شهر

- موقعیت شغلی در **منطقه اکسیتانی** (34, 31, 30, 66, …) → `Montpellier, mobile en France`
- هر جای دیگه → `Grenoble, mobile en France`
- پیاده‌سازی: `src/core/location_utils.py` → `select_cv_city(job_location, language)`
- برای candidature spontanée: `--city montpellier` یا `--city grenoble`

---

## تصمیمات مهم (May 2026)

- **gitignore whitelist strategy**: همه چیز ignore، فقط `.tex .md .sh .py .js .mjs .cls .env.example .gitignore master_cv.example.json` whitelist شده‌اند
- **git filter-repo**: تاریخچه git تمیز شد — فایل‌های sensitive از تمام ۳۸ commit حذف شدند
- **LinkedIn API version**: `202604` (calendar versioning — هر چند ماه باید آپدیت شود)
- **carousel CSS**: `.slide { height:1080px; display:flex; flex-direction:column; justify-content:center }` — vertical centering با DOM wrapping
- **قالب‌های جدید (May 2026):** 16 قالب classic (moderncv banking)، 4 قالب altacv (AI MLOps en/fr، DevOps Alternance، Polyvalent)، 1 قالب lato/PhD Research، 2 قالب tina
- **candidature spontanée (May 2026):** `build_spontaneous()` در `latex_builder.py`، `generate_spontaneous()` در `service.py`، دستور CLI: `uv run main.py spontaneous <role>`
- **`ApplicationBundle.cl_pdf`**: از `Path` به `Path | None` تغییر کرد — برای candidature spontanée که cover letter ندارد
- **نامگذاری خروجی:** pattern ثابت `{CV_OWNER_SLUG}-{DocumentType}_{Role}_{lang}.pdf` — برای tailored و spontaneous یکسان؛ پوشه spontanée از نام شرکت خالی است (`Spontannee_{role}_{lang}`). `CV_OWNER_SLUG` باید در `.env` ست شود.
- **`build_spontaneous` output folder:** فقط `.cls/.sty` از پوشه template کپی می‌شود (نه همه قالب‌ها) — خروجی تمیز

---

## تصمیمات مهم (22 مه 2026) — سیستم tailored pipeline

### LLM model
- **`LLM_MODEL=deepseek-v4-flash`** در `.env` — مدل DeepSeek جایگزین `gpt-4o-mini` شد.
  اگر خطای `model not found` دیدی، مطمئن شو `.env` این مقدار را دارد.

### `conditional_education` — مدرک شرطی
- پروفایل‌های source JSON می‌توانند آرایه `conditional_education` داشته باشند.
- هر entry دارای `relevant_domains` است (مثل `["maintenance", "ferroviaire", "electronique"]`).
- `format_for_prompt()` در `resume_loader.py` این بخش را به LLM می‌دهد.
- LLM مدرک را **فقط اگر** حوزه شغل با `relevant_domains` تطبیق دارد در `extra_education` می‌گذارد.
- برای نقش‌های AI/Data/IT محض، `extra_education` خالی برمی‌گردد.

### `selected_education` و space budget rule
- LLM لیست `selected_education` را با اختیار trim کردن `honors` کنترل می‌کند.
- **Space budget rule:** وقتی `extra_education` غیر‌خالی است، LLM باید از راست جبران کند:
  1. حذف جزئی‌ترین grade ها از `honors`
  2. کاهش `selected_projects` به حداکثر ۱ پروژه
  3. فقط در آخرین حالت: کاهش highlights به ۲ مورد
- **⛔ ستون چپ قفل است:** هرگز `tailored_skills`، category‌های skills، certifications، languages یا hobbies حذف نمی‌شوند.

### Dynamic cover letter — `cl_intro` + `cl_body`
- قالب `Cover_Letter_Template_Fr.tex` دیگر `\ifthenelse` ندارد.
- LLM دو پاراگراف کاملاً متناسب با آگهی تولید می‌کند: `cl_intro` (معرفی + دیپلم) و `cl_body` (یک دستاورد کلیدی).
- `latex_builder.py` در `_fill_cover_letter` این مقادیر را به `\newcommand{\CLIntro}` و `\newcommand{\CLBody}` inject می‌کند.
- برای مشاغل غیر IT (مثل نگهداری قطار)، LLM باید transferable skills را تأکید کند.

### Personal data injection در cover letter
- `_fill_cover_letter` اکنون `templates/shared/personal_data.tex` را می‌خواند و `\providecommand` placeholder ها را با مقادیر واقعی جایگزین می‌کند.
- بدون این، `\cvname{Firstname LASTNAME}` و سایر placeholder‌ها در CL باقی می‌ماندند.

### `_strip_years_and_metrics()` — post-processing
- `content_tailor.py` تابع `_strip_years_and_metrics()` دارد که روی `why_this_company`، `cv_summary`، `cl_intro` و `cl_body` اجرا می‌شود.
- الگوهای حذف: `"X ans d'expérience"`, `"plus de X ans"`, `"X+ years"`, و درصدها (`±N%`).
- قانون در prompt هم تعریف شده: سال‌ها فقط وقتی آگهی به‌صراحت N سال خواسته مجاز است.

### `--color blue` به عنوان پیش‌فرض
- `amir apply` به‌صورت پیش‌فرض `--color blue` به pipeline اضافه می‌کند.
- می‌توان override کرد: `amir apply <url> --color green`
- رنگ `blue` = `\backgroundcolor{c[0]}[HTML]{E6F0FA}` در altacv.
