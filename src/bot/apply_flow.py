"""
apply_flow.py — Telegram handler for the /apply command.

Flow:
    1. User sends /apply <url>  (or replies to a message containing a link)
    2. Bot scrapes the URL, classifies role, tailors content, compiles PDFs
    3. If AUTO_APPLY → archive immediately
       Else → send both PDFs with Approve / Reject buttons
    4. On approval → archive to the private channel

Adapted from Multi_Agent_Job_Applier/src/bot/apply_flow.py.
Key change: handles a bundle of (cv_pdf, cl_pdf) instead of a single file.
"""
from __future__ import annotations

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.bot.archiver import archive_sync
from src.core.logger import logger
from src.core.settings import AUTO_APPLY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.pipeline.service import ApplicationService


class ApplyFlow:
    def __init__(self, service: ApplicationService) -> None:
        self.service = service

    # ── /apply command ────────────────────────────────────────────────────────

    async def handle_apply(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        url = self._extract_url(message, context)

        if not url:
            await message.reply_text(
                "❌ No job URL found.\n"
                "Usage: `/apply <url>`  or reply to a message containing a link.",
                parse_mode="Markdown",
            )
            return

        await message.reply_text(
            f"⏳ Analyzing job posting and generating application…\n`{url}`",
            parse_mode="Markdown",
        )

        try:
            bundle = self.service.generate(job_url=url)
        except Exception as exc:
            logger.error(f"Pipeline failed for {url}: {exc}", exc_info=True)
            await message.reply_text(f"❌ Generation failed: {exc}")
            return

        if AUTO_APPLY:
            await message.reply_text("✅ AUTO_APPLY enabled — archiving…")
            self._archive(bundle, url)
            await message.reply_text("🎉 Application archived!")
            return

        # Send both PDFs with Approve / Reject buttons
        caption = (
            f"📝 *Review Application*\n"
            f"Job: `{url}`\n\n"
            f"Approve to archive both CV + Cover Letter to your channel."
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Approve & Archive",
                        callback_data=f"approve|{bundle.cv_pdf}|{bundle.cl_pdf}|{url}",
                    ),
                    InlineKeyboardButton("❌ Reject", callback_data="reject"),
                ]
            ]
        )

        # Send CV
        with open(bundle.cv_pdf, "rb") as f:
            await message.reply_document(document=f, filename=bundle.cv_pdf.name)

        # Send CL with buttons
        with open(bundle.cl_pdf, "rb") as f:
            await message.reply_document(
                document=f,
                filename=bundle.cl_pdf.name,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

    # ── Callback (Approve / Reject) ───────────────────────────────────────────

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        parts = query.data.split("|")
        action = parts[0]

        if action == "reject":
            await query.edit_message_caption(caption="❌ Application rejected.")
            return

        if action == "approve" and len(parts) >= 4:
            from pathlib import Path

            cv_pdf = Path(parts[1])
            cl_pdf = Path(parts[2])
            url = parts[3]

            await query.edit_message_caption(caption="✅ Approved — archiving…")
            archive_sync(
                token=TELEGRAM_BOT_TOKEN,
                channel_id=TELEGRAM_CHAT_ID,
                company="Application",
                position="Position",
                cv_pdf=cv_pdf,
                cl_pdf=cl_pdf,
                job_url=url,
            )
            await query.edit_message_caption(caption="🎉 Application archived!")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_url(message, context) -> str | None:
        if context.args:
            return context.args[0]
        if message.reply_to_message:
            text = message.reply_to_message.text or message.reply_to_message.caption or ""
            urls = re.findall(r"https?://\S+", text)
            if urls:
                return urls[0]
        # Also handle a bare link sent directly (no /apply prefix)
        if message.text:
            urls = re.findall(r"https?://\S+", message.text)
            if urls:
                return urls[0]
        return None

    def _archive(self, bundle, url: str) -> None:
        archive_sync(
            token=TELEGRAM_BOT_TOKEN,
            channel_id=TELEGRAM_CHAT_ID,
            company="Application",
            position="Position",
            cv_pdf=bundle.cv_pdf,
            cl_pdf=bundle.cl_pdf,
            job_url=url,
        )

    # ── Register handlers onto a dispatcher ──────────────────────────────────

    def register(self, application) -> None:
        application.add_handler(CommandHandler("apply", self.handle_apply))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
