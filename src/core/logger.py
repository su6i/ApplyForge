"""
Centralized logger using loguru.
All modules import `logger` from here.
"""
import os
from loguru import logger

os.makedirs("log", exist_ok=True)

logger.add(
    "log/cv_bot.log",
    rotation="10 MB",
    retention="1 week",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
)
