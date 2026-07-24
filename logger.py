"""
Centralized logging configuration using loguru.
Import `logger` anywhere in the project for consistent logging.
"""
import sys
from loguru import logger
from config import settings

logger.remove()  # remove default handler
logger.add(
    sys.stdout,
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
)
logger.add(
    "logs/bmtc_rag_{time:YYYY-MM-DD}.log",
    level=settings.LOG_LEVEL,
    rotation="1 day",
    retention="14 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
)

__all__ = ["logger"]
