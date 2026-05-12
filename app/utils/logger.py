import logging
import os

from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "organizerr.log"


LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)s | "
    "%(name)s | "
    "%(message)s"
)


def setup_logging():

    formatter = logging.Formatter(LOG_FORMAT)

    root_logger = logging.getLogger()

    root_logger.setLevel(LOG_LEVEL)

    # Prevent duplicate handlers
    if root_logger.handlers:
        return

    # -----------------------------
    # Console handler
    # -----------------------------
    console_handler = logging.StreamHandler()

    console_handler.setLevel(LOG_LEVEL)

    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    # -----------------------------
    # Rotating file handler
    # -----------------------------
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )

    file_handler.setLevel(LOG_LEVEL)

    file_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)

    # Reduce noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info("Logging initialized")


def get_logger(name: str):
    return logging.getLogger(name)