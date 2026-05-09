"""
logger.py
---------
Sets up a named logger with:
  - A rich console handler (color-coded by level)
  - An optional rotating file handler

Design decisions:
  - Uses Python's built-in logging to avoid heavy dependencies.
  - A single `get_logger()` factory ensures all modules share the same
    named logger, so handlers are never duplicated across imports.
  - RotatingFileHandler caps log size at 5 MB with 3 backups — safe for
    long-running sessions without eating disk space.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# ANSI colour codes (Windows 10+ and all major terminals support these)
# ---------------------------------------------------------------------------

_RESET  = "\x1b[0m"
_BOLD   = "\x1b[1m"

_LEVEL_COLORS = {
    logging.DEBUG:    "\x1b[36m",   # Cyan
    logging.INFO:     "\x1b[32m",   # Green
    logging.WARNING:  "\x1b[33m",   # Yellow
    logging.ERROR:    "\x1b[31m",   # Red
    logging.CRITICAL: "\x1b[35m",   # Magenta
}


class _ColorFormatter(logging.Formatter):
    """Formatter that adds ANSI colours to the level name on supporting terminals."""

    FMT = "%(asctime)s  %(levelname)-8s  %(message)s"
    DATE_FMT = "%H:%M:%S"

    def __init__(self, use_color: bool = True) -> None:
        super().__init__(fmt=self.FMT, datefmt=self.DATE_FMT)
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        formatted = super().format(record)
        if self._use_color:
            color = _LEVEL_COLORS.get(record.levelno, "")
            level_str = f"{color}{_BOLD}{record.levelname:<8}{_RESET}"
            # Replace plain level name in the already-formatted string
            formatted = formatted.replace(record.levelname.ljust(8), level_str, 1)
        return formatted


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

_LOGGER_NAME = "file_organizer"


def get_logger(
    name: str = _LOGGER_NAME,
    level: int = logging.INFO,
    log_to_file: bool = False,
    log_file: Optional[str | Path] = None,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> logging.Logger:
    """
    Return (or create) the shared application logger.

    Parameters
    ----------
    name         : Logger name; child loggers share the same handlers.
    level        : Minimum severity to emit.
    log_to_file  : Whether to also write logs to a rotating file.
    log_file     : Path for the log file (defaults to 'organizer.log' in cwd).
    max_bytes    : Maximum size per log file before rotation.
    backup_count : Number of rotated files to keep.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls (e.g. during tests)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # --- Console handler ---
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    use_color = sys.stdout.isatty()  # Disable colour when piped / redirected
    console.setFormatter(_ColorFormatter(use_color=use_color))
    logger.addHandler(console)

    # --- File handler (optional) ---
    if log_to_file:
        path = Path(log_file) if log_file else Path("organizer.log")
        file_handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # Capture everything in the file
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s  %(levelname)-8s  %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)

    return logger


def get_child_logger(module_name: str) -> logging.Logger:
    """
    Return a child logger scoped to a specific module.

    Example: get_child_logger("scanner") → 'file_organizer.scanner'
    All output still flows through the root app logger's handlers.
    """
    return logging.getLogger(f"{_LOGGER_NAME}.{module_name}")
