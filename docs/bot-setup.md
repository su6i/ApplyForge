# Telegram Bot — Setup & Configuration

[Back to README](../README.md) | [Architecture](architecture.md) | [LaTeX Templates](latex-templates.md) | [Git Workflow](git-workflow.md)

## Prerequisites

- Python 3.11+
- TeX Live 2024+ with `pdflatex` and `xelatex` in `PATH`
- A Telegram account
- An OpenAI API key

---

## Installation

```bash
# From the repo root
pip install -r requirements.txt
cp .env.example .env
```

---

## Environment Variables

Edit `.env` (never commit this file — it is in `.gitignore`):

```ini
# Required for ALL modes
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini         # optional, this is the default

# Required for bot mode and archiving
TELEGRAM_BOT_TOKEN=12345:ABC...
TELEGRAM_CHAT_ID=-100123...   # the channel/group where PDFs are archived

# Optional
AUTO_APPLY=false              # set "true" to archive without approval buttons
```

### Getting Telegram credentials

**Bot token:**
1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow the prompts
3. Copy the token into `TELEGRAM_BOT_TOKEN`

**Chat ID (private archive channel):**
1. Create a private channel in Telegram
2. Add your bot as an **administrator** with "Post messages" permission
3. Forward a message from the channel to `@userinfobot` — it returns the chat ID
4. Paste the ID (starts with `-100…`) into `TELEGRAM_CHAT_ID`

---

## Running

### Bot mode (recommended)
```bash
uv run main.py bot
```
Then in Telegram:
```
/apply https://company.com/jobs/data-scientist-123
```
The bot replies with two PDFs and **Approve / Reject** buttons.
- **Approve** → both files are forwarded to your archive channel.
- **Reject** → nothing is saved.

### CLI mode (no Telegram needed)
```bash
uv run main.py apply https://company.com/jobs/123 [--template altacv|lato]
```
PDFs are saved to `Applied/YYYY-MM_Company_Role/` and paths are printed.

### Configuration check
```bash
uv run main.py test
```
Prints all settings, checks that template folders exist, and verifies that
`pdflatex` and `xelatex` are in `PATH`.

---

## AUTO_APPLY Mode

When `AUTO_APPLY=true` in `.env`:
- The bot archives both PDFs immediately after generation — no buttons shown.
- Useful for batch processing or when you trust the pipeline output.

---

## Apply Flow (step by step)

```
User: /apply https://...
  │
  Bot: "⏳ Analyzing…"
  │
  Pipeline: scrape → classify → tailor → compile
  │
  Bot: sends CV.pdf + "Review Application" [Approve] [Reject]
        ↓ Approve
  Bot: forwards both PDFs to archive channel
       sends "🎉 Application archived!"
        ↓ Reject
  Bot: edits caption → "❌ Application rejected."
```

---

## Source Files

| File | Purpose |
|---|---|
| `src/bot/bot.py` | `CVBot` class — builds the Telegram `Application`, registers handlers, calls `.run_polling()` |
| `src/bot/apply_flow.py` | `ApplyFlow` — handles `/apply` command and Approve/Reject callbacks |
| `src/bot/archiver.py` | `archive_sync()` — sends both PDFs to the private channel via Bot API |
| `src/core/settings.py` | Reads all env vars from `.env`; exposes typed constants |
| `src/core/logger.py` | Loguru logger writing to `log/cv_bot.log` (rotation 10 MB, retention 1 week) |
