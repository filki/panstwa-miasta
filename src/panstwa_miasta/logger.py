# logger.py – Central logging configuration for the Państwa‑Miasta project
"""Utility module providing a configured :pyclass:`logging.Logger` instance.

Best‑practice highlights:
- **Single source of truth** – All modules import ``get_logger`` to obtain a
  consistently‑configured logger.
- **Configurable via environment** – ``LOG_LEVEL`` and ``LOG_FILE`` can be set
  without code changes.
- **Rotating file handler** – Prevents unbounded log file growth.
- **Console handler** – Human‑readable logs during development.
- **Structured format** – Timestamp, level, module, line number and message.
- **Thread‑safe** – Handlers are added only once (module‑level singleton).

Usage::

    from .logger import get_logger
    logger = get_logger(__name__)
    logger.info("Server started")
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration (environment variables – fallback defaults)
# ---------------------------------------------------------------------------
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10 MiB
BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# Convert textual level to ``logging`` constant, defaulting to INFO on error.
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# Ensure the log directory exists.
log_path = Path(LOG_FILE).expanduser().resolve()
log_path.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Formatter – one line, ISO‑8601 timestamp, level, module and line number.
# ---------------------------------------------------------------------------
formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Handlers – file (rotating) and console (stream). Added only once.
# ---------------------------------------------------------------------------
_file_handler = RotatingFileHandler(
    filename=str(log_path),
    maxBytes=MAX_BYTES,
    backupCount=BACKUP_COUNT,
    encoding="utf-8",
)
_file_handler.setLevel(LOG_LEVEL)
_file_handler.setFormatter(formatter)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(LOG_LEVEL)
_console_handler.setFormatter(formatter)

# ---------------------------------------------------------------------------
# Helper to retrieve a logger with the shared configuration.
# ---------------------------------------------------------------------------
def get_logger(name: str = "panstwa_miasta") -> logging.Logger:
    """Return a logger with pre‑configured handlers.

    The function is idempotent – repeated calls for the same *name* will not
    re‑attach handlers, avoiding duplicate log entries.
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # Attach handlers only once per logger instance.
    if not logger.handlers:
        logger.addHandler(_file_handler)
        logger.addHandler(_console_handler)
        # Avoid propagating to the root logger (which may have its own handlers).
        logger.propagate = False
    return logger

# Provide a module‑level default logger for quick imports.
default_logger = get_logger()

__all__ = ["get_logger", "default_logger"]
