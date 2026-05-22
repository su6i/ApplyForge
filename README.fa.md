<div align="center">
  <img src="assets/project_logo.jpg" width="350" alt="لوگوی اپلای‌فورج">
  <h1>اپلای‌فورج - ابزار خودکار تولید رزومه و کاور لتر</h1>

  <br>

  <p align="center" style="white-space: nowrap;">
    <img src="https://img.shields.io/badge/%D9%86%D8%B3%D8%AE%D9%87-0.1.0-blue.svg" alt="نسخه">&nbsp;<img src="https://img.shields.io/badge/%D9%BE%D8%A7%DB%8C%D8%AA%D9%88%D9%86-3.12+-yellow.svg" alt="پایتون">&nbsp;<img src="https://img.shields.io/badge/%D9%85%D8%AC%D9%88%D8%B2-MIT-green.svg" alt="مجوز">&nbsp;<a href="https://www.linkedin.com/in/su6i/"><img src="assets/linkedin_su6i.svg" height="20" alt="لینکدین"></a>
  </p>
</div>

این مخزن ابزار تولید و ارسال خودکار رزومه و نامهٔ پوششی از روی آگهی شغلی است.

نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

پیکربندی

- از روی ` .env.example` یک فایل ` .env` بسازید و مقادیر را تکمیل کنید:
  - `OPENAI_API_KEY` — کلید OpenAI
  - `TELEGRAM_BOT_TOKEN` — توکن بات تلگرام (اختیاری اگر از بات استفاده نمی‌کنید)
  - `TELEGRAM_CHAT_ID` — شناسه چت برای ارسال‌ها

دستورالعمل‌های رایج

- تولید آزمایشی:

```bash
uv run main.py test
```

- تولید رزومه و نامهٔ پوششی برای یک آگهی:

```bash
uv run main.py apply <JOB_URL>
```

- اجرای بات تلگرام (اگر پیکربندی شده):

```bash
uv run main.py bot
```

ساخت LaTeX

اسکریپت `compile.sh` کلیه قالب‌ها را پیدا و می‌سازد؛ نیاز به داشتن `pdflatex`/`xelatex` در مسیر دارد.

مکان خروجی

نسخه‌های تولیدشده در پوشه‌های `Applied/` و `output/` قرار می‌گیرند (قواعد نام‌گذاری در مستندات).

مستندات فنی

مستندات توسعه‌دهنده و معماری را در پوشهٔ `docs/` ببینید. نسخهٔ فارسی آن‌ها در `docs/fa/` قرار دارد.
