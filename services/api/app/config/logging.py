"""Logging configuration for the API service."""

import logging.config
import os
from typing import Dict, Any
from . import settings


def configure_logging():
    """Configure logging for the application."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "detailed",
                "filename": settings.log_file,
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
            },
        },
        "loggers": {
            "app": {  # Logger for all app.* modules
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "app.graph.nodes.risk_ml": {  # Specific logger for risk ML
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "app.graph.nodes.health": {  # Specific logger for health node
                "level": "INFO",  # Default to INFO but allow override
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "app.graph.nodes.places": {  # Specific logger for places node
                "level": "DEBUG",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
        "root": {  # Root logger
            "level": "WARNING",
            "handlers": ["console"],
        },
    }

    # Ensure log directory exists
    log_dir = os.path.dirname(settings.log_file)
    os.makedirs(log_dir, exist_ok=True)

    # Apply configuration
    logging.config.dictConfig(config)
