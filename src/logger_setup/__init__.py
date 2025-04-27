"""Application-wide logging configuration.

This small helper wires up **loguru** so that:

1. All log messages are emitted to *stdout* (human-readable colours) – no
   file handlers are created.
2. The log level can be overridden via the ``HEWS_LOG_LEVEL`` environment
   variable (defaults to ``INFO``).

The module should be imported **once** at the very beginning of the
application entry-point (e.g., in ``main.py`` or ``cli.py``) so that the
configuration is applied before other modules start logging.
"""

from __future__ import annotations

import os
import sys
from typing import Final

from loguru import logger as _logger


_DEFAULT_LEVEL: Final[str] = os.getenv("HEWS_LOG_LEVEL", "INFO").upper()


def _configure() -> None:
    """Configure loguru to output to stdout only."""

    # Remove the default handler that logs to stderr.
    _logger.remove()

    # Add a new handler that writes colourful, pretty logs to stdout with
    # millisecond timestamps.
    _logger.add(
        sys.stdout,
        level=_DEFAULT_LEVEL,
        colorize=True,
        backtrace=False,
        diagnose=False,
        enqueue=True,  # Use background thread for I/O so TUI stays snappy.
    )


# Apply configuration immediately upon import.
_configure()

# Re-export the configured logger so callers can simply do:
#     from logger_setup import logger
# without worrying about configuration.

logger = _logger

__all__ = ["logger"]
