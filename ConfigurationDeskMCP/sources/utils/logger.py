"""Stderr-only structured JSON logger. stdout is reserved for MCP JSON-RPC transport.

On stdio transport, INFO/DEBUG are silent (no stderr noise). Set LOG_LEVEL=DEBUG to enable them.
WARNING+ always write to stderr.
"""

from __future__ import annotations

import logging
import sys
from typing import ClassVar


class _StderrOnlyHandler(logging.StreamHandler):
    """StreamHandler hard-wired to stderr."""

    def __init__(self) -> None:
        super().__init__(stream=sys.stderr)
        self.addFilter(logging.Filter())
        self.setLevel(logging.WARNING)


_LOG_FORMAT = (
    '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
)
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_configured: ClassVar[set[str]] = set()  # type: ignore


def get_logger(name: str) -> logging.Logger:
    """Return a named logger writing structured JSON to stderr. Safe to call multiple times."""
    logger = logging.getLogger(name)

    if name not in _configured:
        handler = _StderrOnlyHandler()
        handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        _configured.add(name)

    return logger


def configure_root_level(level: str) -> None:
    """Apply *level* to every logger managed by this module. Called once at startup."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    for name in _configured:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        for h in logger.handlers:
            if isinstance(h, _StderrOnlyHandler):
                h.setLevel(numeric if numeric <= logging.DEBUG else logging.WARNING)
