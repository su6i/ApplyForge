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
| `src/pipeline/` | Pipeline پردازش: scraping، LLM، compile |
| `templates/lato/` | قالب‌های LaTeX رزومه |
| `cover_letters/` | قالب‌های LaTeX کاور لتر |
| `compile.sh` | ساخت PDF از LaTeX (`./compile.sh ai|it|phd|all`) |
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
# تولید رزومه + کاور لتر از URL شغلی
uv run main.py apply https://company.com/jobs/12345

# ساخت PDF از LaTeX
./compile.sh ai    # AI / Data Science
./compile.sh it    # IT Support
./compile.sh all   # همه
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

# ۲. نصب وابستگی‌ها
pip install -r requirements.txt

# ۳. برای LinkedIn (اختیاری)
python scripts/linkedin_post.py --auth
```

---

## تصمیمات مهم (May 2026)

- **gitignore whitelist strategy**: همه چیز ignore، فقط `.tex .md .sh .py .js .mjs .env.example .gitignore master_cv.example.json` whitelist شده‌اند
- **git filter-repo**: تاریخچه git تمیز شد — فایل‌های sensitive از تمام ۳۸ commit حذف شدند
- **LinkedIn API version**: `202604` (calendar versioning — هر چند ماه باید آپدیت شود)
- **carousel CSS**: `.slide { height:1080px; display:flex; flex-direction:column; justify-content:center }` — vertical centering با DOM wrapping
