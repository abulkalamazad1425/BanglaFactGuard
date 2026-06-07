"""
app/core/logging.py
===================
Structured, JSON-formatted logging for BanglaFactGuard using structlog.

Design decisions:
- structlog is chosen over standard `logging` for native structured context
  binding, consistent JSON output, and first-class async support.
- In production (`log_format="json"`), every log line is a JSON object with
  timestamp, level, logger name, request_id, claim_id, stage_id, and message.
- In development (`log_format="console"`), structlog renders colourised,
  human-readable output via ConsoleRenderer.
- `setup_logging()` must be called ONCE at application startup (in `main.py`
  lifespan). Subsequent calls are idempotent.
- `get_logger()` returns a bound structlog logger. Pass it through dependency
  injection or instantiate it at module level — both patterns are safe.
- `bind_request_context()` / `bind_pipeline_context()` helpers allow stages
  and handlers to add contextual fields without repeating `.bind()` calls.

Usage::

    from app.core.logging import get_logger
    logger = get_logger(__name__)

    logger.info("stage_started", stage="s03_query_generator", claim_id=str(claim_id))
    logger.warning("search_fallback", provider="brave", reason="rate_limited")
    logger.error("extraction_failed", url=url, exc_info=True)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import FilteringBoundLogger

from app.core.config import AppSettings, get_settings


# ---------------------------------------------------------------------------
# Processor chains
# ---------------------------------------------------------------------------

# Processors shared by both JSON and console output
_SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,          # Merge context vars (e.g. request_id)
    structlog.stdlib.add_logger_name,                 # Add "logger" field
    structlog.stdlib.add_log_level,                   # Add "level" field
    structlog.stdlib.PositionalArgumentsFormatter(),  # Handle %s-style formatting
    structlog.processors.TimeStamper(fmt="iso"),      # ISO-8601 timestamp
    structlog.processors.StackInfoRenderer(),         # Render stack_info if present
    structlog.processors.format_exc_info,             # Format exc_info as string
    structlog.processors.UnicodeDecoder(),            # Ensure all strings are unicode
]

_JSON_PROCESSORS: list[Any] = [
    *_SHARED_PROCESSORS,
    structlog.processors.dict_tracebacks,             # Structured tracebacks in JSON
    structlog.processors.JSONRenderer(),              # Final JSON serialisation
]

_CONSOLE_PROCESSORS: list[Any] = [
    *_SHARED_PROCESSORS,
    structlog.dev.ConsoleRenderer(colors=True),       # Human-readable colourised output
]


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def setup_logging(settings: AppSettings | None = None) -> None:
    """
    Configure structlog and the stdlib `logging` module.

    Must be called once at application startup before any loggers are used.
    Subsequent calls are safe (idempotent due to stdlib logging's existing
    handler check).

    Args:
        settings: AppSettings instance. If None, uses `get_settings()`.
    """
    if settings is None:
        settings = get_settings()

    log_level_int = getattr(logging, settings.log_level, logging.INFO)

    # --- Configure stdlib logging as the backend ---------------------------
    # structlog delegates actual I/O to stdlib so third-party libraries
    # (uvicorn, sqlalchemy, httpx) integrate seamlessly.
    logging.basicConfig(
        format="%(message)s",        # structlog handles the full format
        stream=sys.stdout,
        level=log_level_int,
        force=True,                  # Override any earlier basicConfig calls
    )

    # Silence noisy stdlib loggers in non-debug mode
    if settings.log_level != "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # --- Configure structlog -----------------------------------------------
    processors = (
        _JSON_PROCESSORS
        if settings.log_format == "json"
        else _CONSOLE_PROCESSORS
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level_int),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    """
    Return a structlog bound logger.

    Args:
        name: Logger name, typically ``__name__``. If None, structlog infers
              from the call stack.

    Returns:
        A structlog FilteringBoundLogger pre-bound with the logger name.

    Example::

        logger = get_logger(__name__)
        logger.info("verification_started", claim_id=str(claim_id))
    """
    return structlog.get_logger(name)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def bind_request_context(
    request_id: str,
    *,
    endpoint: str | None = None,
    client_ip: str | None = None,
) -> None:
    """
    Bind HTTP request-level fields into structlog's context vars.

    Call this at the start of each request (in middleware) so every log line
    emitted during that request automatically includes `request_id`.

    Args:
        request_id: Unique identifier for the HTTP request (UUID string).
        endpoint:   The matched route path (e.g. "/api/v1/verify").
        client_ip:  Originating client IP address.
    """
    ctx: dict[str, Any] = {"request_id": request_id}
    if endpoint:
        ctx["endpoint"] = endpoint
    if client_ip:
        ctx["client_ip"] = client_ip
    structlog.contextvars.bind_contextvars(**ctx)


def bind_pipeline_context(
    claim_id: str,
    *,
    stage_id: str | None = None,
    normalized_source: str | None = None,
) -> None:
    """
    Bind pipeline-level fields into structlog's context vars.

    Call this at the start of each pipeline run (in the orchestrator) so
    every stage's log lines include `claim_id` without explicit passing.

    Args:
        claim_id:          UUID string of the verified_claims record.
        stage_id:          Optional current stage identifier (update per stage).
        normalized_source: Resolved canonical domain for the claim.
    """
    ctx: dict[str, Any] = {"claim_id": claim_id}
    if stage_id:
        ctx["stage_id"] = stage_id
    if normalized_source:
        ctx["normalized_source"] = normalized_source
    structlog.contextvars.bind_contextvars(**ctx)


def clear_context() -> None:
    """
    Clear all structlog context vars.

    Call at the end of each request (in middleware) to prevent context
    leakage between requests on the same async worker.
    """
    structlog.contextvars.clear_contextvars()
