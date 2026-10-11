"""Logging for TripGenie: prints to the console and writes to logs/tripgenie.log."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Always next to the project, no matter where you start the app from
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

# Streamlit runs the whole script again on every click.
# This flag makes sure we set up logging only ONCE (no repeated banners, no leaked files).
_logging_ready = False


def setup_logging(log_level: str = "INFO", log_to_file: bool = True) -> None:
    """Set up logging. Safe to call many times - only the first call does anything."""
    global _logging_ready
    if _logging_ready:
        return
    _logging_ready = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 1) Console
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(console)

    # 2) File. When it reaches 1 MB a new file is started (3 old files are kept).
    if log_to_file:
        LOG_DIR.mkdir(exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_DIR / "tripgenie.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )
        root.addHandler(file_handler)

    # These libraries are very chatty, only show their warnings
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "streamlit", "primp", "ddgs"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info("Logging started")


class TripGenieLogger:
    """A small wrapper around the standard logger with a few helpful extra methods."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str, exc: Optional[BaseException] = None) -> None:
        """Log an error. Pass the exception as exc to also record the stack trace."""
        self.logger.error(message, exc_info=exc)

    # ---- Special helpers -------------------------------------------------

    def log_user_action(self, action: str, details: Optional[dict] = None) -> None:
        """Record something the user did (for example 'generate_plan')."""
        text = f"User action: {action}"
        if details:
            text += f" | {details}"
        self.logger.info(text)

    def log_tool_call(self, tool: str, query: str, result_count: int, seconds: float) -> None:
        """Record a web search, so you can always see what was really searched."""
        self.logger.info(f"Tool call: {tool} | query='{query}' | results={result_count} | {seconds:.2f}s")

    def log_search(self, query: str, result_count: int, seconds: float) -> None:
        """Record a location search."""
        self.logger.info(f"Location search: '{query}' | results={result_count} | {seconds:.2f}s")


def get_logger(name: str) -> TripGenieLogger:
    """Get a logger:  logger = get_logger(__name__)"""
    return TripGenieLogger(name)
