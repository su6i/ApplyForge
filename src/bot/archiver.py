"""
archiver.py — Send compiled application documents to a Telegram channel.

Adapted from Multi_Agent_Job_Applier/src/bot/archiver.py.
Key change: now sends both cv_pdf AND cl_pdf.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from telegram import Bot

from src.core.logger import logger


class Archiver:
    def __init__(self, token: str, channel_id: str) -> None:
        self.bot = Bot(token)
        self.channel_id = channel_id

    async def archive(
        self,
        company: str,
        position: str,
        cv_pdf: Path,
        cl_pdf: Path,
        job_url: str = "",
    ) -> None:
        caption = (
            f"📄 *Application Archived*\n\n"
            f"*Company:* {company}\n"
            f"*Position:* {position}"
        )
        if job_url:
            caption += f"\n*URL:* {job_url}"

        try:
            if cv_pdf.exists():
                with open(cv_pdf, "rb") as f:
                    await self.bot.send_document(
                        chat_id=self.channel_id,
                        document=f,
                        filename=cv_pdf.name,
                        caption=caption,
                        parse_mode="Markdown",
                    )
            else:
                logger.warning(f"CV PDF not found: {cv_pdf}")

            if cl_pdf.exists():
                with open(cl_pdf, "rb") as f:
                    await self.bot.send_document(
                        chat_id=self.channel_id,
                        document=f,
                        filename=cl_pdf.name,
                        caption=f"Cover Letter — {company}",
                    )
            else:
                logger.warning(f"Cover letter PDF not found: {cl_pdf}")

            logger.info(f"Archived application: {company} — {position}")

        except Exception as exc:
            logger.error(f"Archive failed: {exc}")
            raise


def archive_sync(
    token: str,
    channel_id: str,
    company: str,
    position: str,
    cv_pdf: Path,
    cl_pdf: Path,
    job_url: str = "",
) -> None:
    """Synchronous wrapper — safe to call from both sync and async contexts."""
    if not token or not channel_id:
        logger.warning("Telegram token or channel ID missing — skipping archive.")
        return

    archiver = Archiver(token, channel_id)

    async def _run():
        await archiver.archive(company, position, cv_pdf, cl_pdf, job_url)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())
