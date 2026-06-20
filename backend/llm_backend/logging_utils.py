"""Logging helpers for structured, low-dependency log records."""

from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Return a module logger without forcing application logging config."""
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    **fields: Any,
) -> None:
    """Emit a structured log event using the stdlib logger extra channel."""
    logger.log(level, message, extra={"event": event, "fields": fields})
