"""Shared logging helpers for crawler engines."""

from __future__ import annotations

import logging
from typing import Optional


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger with a simple console handler."""
    logger = logging.getLogger(name)
    if logger.handlers:
        logger.setLevel(level)
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def child_logger(parent_name: str, suffix: str, level: Optional[int] = None) -> logging.Logger:
    name = f"{parent_name}.{suffix}"
    logger = get_logger(name)
    if level is not None:
        logger.setLevel(level)
    return logger
