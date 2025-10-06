from __future__ import annotations
import os
import logging
import contextvars
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


_rid_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            record.request_id = _rid_var.get()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive fallback
            record.request_id = "-"  # type: ignore[attr-defined]
        return True


def set_request_id(rid: str) -> None:
    try:
        _rid_var.set(rid)
    except Exception:  # pragma: no cover - defensive fallback
        _rid_var.set("-")


def clear_request_id() -> None:
    _rid_var.set("-")


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

    fmt = logging.Formatter(
        "%(asctime)s | [%(levelname)s] [%(name)s] rid=%(request_id)s %(message)s"
    )
    fileh = RotatingFileHandler(logfile, maxBytes=2_000_000, backupCount=2)
    fileh.setFormatter(fmt)
    fileh.addFilter(RequestIdFilter())
    rooth = logging.StreamHandler()
    rooth.setFormatter(fmt)
    rooth.addFilter(RequestIdFilter())

    root.addHandler(fileh)
    root.addHandler(rooth)

    logging.getLogger(__name__).info("Logging to %s", logfile)
    return logfile
