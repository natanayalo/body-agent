from __future__ import annotations
import os
import logging
import tempfile
from pathlib import Path
from logging.handlers import RotatingFileHandler


def _resolve_log_dir() -> Path:
    # Prefer explicit override; then APP_DATA_DIR/logs; finally /tmp
    base = os.getenv("APP_LOG_DIR")
    if base:
        return Path(base)
    data = os.getenv("APP_DATA_DIR")
    if data:
        return Path(data) / "logs"
    return Path(tempfile.gettempdir()) / "body-agent"


def configure_logging() -> Path:
    log_dir = _resolve_log_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Last-resort fallback
        log_dir = Path(tempfile.gettempdir()) / "body-agent"
        log_dir.mkdir(parents=True, exist_ok=True)

    logfile = log_dir / "api.log"

    root = logging.getLogger()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    root.setLevel(log_level)

    # Clear existing handlers (avoid duplicates under reload)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter("%(asctime)s | [%(levelname)s] [%(name)s] %(message)s")
    fileh = RotatingFileHandler(logfile, maxBytes=2_000_000, backupCount=2)
    fileh.setFormatter(fmt)
    rooth = logging.StreamHandler()
    rooth.setFormatter(fmt)

    root.addHandler(fileh)
    root.addHandler(rooth)

    logging.getLogger(__name__).info("Logging to %s", logfile)
    return logfile
