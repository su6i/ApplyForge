"""
bot.py — Telegram bot entry point.

Commands:
    /start  — greeting
    /apply <url>  — generate tailored CV + cover letter from job URL

Adapted from Multi_Agent_Job_Applier/src/bot/bot.py.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from src.bot.apply_flow import ApplyFlow
from src.core.logger import logger
from src.core.settings import TELEGRAM_BOT_TOKEN
from src.pipeline.service import ApplicationService

_WELCOME = (
    "👋 *CV Bot*\n\n"
    "Send me a job URL and I'll generate a tailored CV + cover letter.\n\n"
    "Usage:\n"
    "`/apply https://example.com/job/123`\n\n"
    "I will:\n"
    "1. Analyze the job posting\n"
    "2. Select the right CV template (AI / IT / PhD)\n"
    "3. Write a personalized cover letter\n"
    "4. Send you both PDFs for review"
)


class CVBot:
    def __init__(self) -> None:
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

        service = ApplicationService()
        self.apply_flow = ApplyFlow(service)

        self.app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.app.add_handler(CommandHandler("start", self._start))
        self.apply_flow.register(self.app)

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(_WELCOME, parse_mode="Markdown")

    def run(self) -> None:
        logger.info("CV Bot polling…")
        self.app.run_polling()
