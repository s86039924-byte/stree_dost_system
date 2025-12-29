"""Structured logging helpers."""
from __future__ import annotations

import logging
from logging.config import dictConfig


def configure_logging(app) -> None:
    """Apply a sane default logging configuration."""
    level = app.config.get("LOG_LEVEL", "INFO")
    dictConfig(
        {
            "version": 1,
            "formatters": {
                "structured": {
                    "format": "%(asctime)s %(levelname)s %(name)s :: %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "structured",
                    "level": level,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
            "disable_existing_loggers": False,
        }
    )
    logging.getLogger(__name__).debug("Logging configured", extra={"level": level})
