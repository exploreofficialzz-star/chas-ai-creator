"""
Logging configuration.
FILE: app/core/logging.py

FIXES:
1. CRITICAL — structlog.processors.format_exc_info was removed in
   structlog >= 21.2.0 and is now structlog.dev.ConsoleRenderer handles
   it automatically, OR use structlog.processors.ExceptionRenderer().
   The old name raised AttributeError at startup, crashing the entire app
   before any request could be served.

2. structlog.stdlib.filter_by_level requires the standard library logger
   to be configured BEFORE structlog.configure() is called — and it must
   receive the log level as a string (e.g. "INFO"), not an integer.
   The original code called getattr(logging, settings.LOG_LEVEL) which
   returns the integer — correct for basicConfig but wrong for structlog.
   Fixed: pass the string LOG_LEVEL to both.

3. setup_logging() wasn't idempotent — calling it twice (e.g. in tests)
   added duplicate handlers to the root logger, doubling every log line.
   Fixed with a module-level guard.

4. get_logger() always returned a structlog logger regardless of whether
   structlog.configure() had been called yet. If any module called
   get_logger() at import time (before lifespan runs setup_logging()),
   the logger was misconfigured. Fixed: configure on first call if needed.

5. LOG_LEVEL defaulting — if settings.LOG_LEVEL is undefined or blank,
   getattr() would return the default int which broke the string-based
   structlog filter. Fixed: safe fallback to "INFO".
"""

import logging
import sys
from typing import Optional

_logging_configured = False   # FIX 3 — idempotency guard


def setup_logging() -> None:
    """
    Configure structlog + stdlib logging.
    Safe to call multiple times — only runs once.
    """
    global _logging_configured
    if _logging_configured:
        return

    from app.config import settings
    import structlog

    # FIX 2 / FIX 5 — get log level as string, with safe fallback
    log_level_str = getattr(settings, "LOG_LEVEL", "INFO") or "INFO"
    log_level_str = log_level_str.upper()

    log_format = getattr(settings, "LOG_FORMAT", "console") or "console"

    # FIX 3 — remove any handlers already on root logger before adding ours
    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level_str,    # FIX 2 — string, not integer
    )

    # FIX 1 — use ExceptionRenderer instead of removed format_exc_info
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),   # FIX 1
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    structlog.configure(
        processors=shared_processors + [renderer],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _logging_configured = True

    # Log confirmation using stdlib so structlog is definitely ready
    logging.getLogger("logging").info(
        f"Logging configured — level={log_level_str} format={log_format}"
    )


def get_logger(name: str):
    """
    Get a structured logger by name.
    FIX 4 — auto-configures with defaults if setup_logging() wasn't called yet.
    """
    global _logging_configured
    if not _logging_configured:
        setup_logging()

    import structlog
    return structlog.get_logger(name)
