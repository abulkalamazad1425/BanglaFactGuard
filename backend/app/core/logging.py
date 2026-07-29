
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import FilteringBoundLogger

from app.core.config import AppSettings, get_settings







_SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
]

_JSON_PROCESSORS: list[Any] = [
    *_SHARED_PROCESSORS,
    structlog.processors.dict_tracebacks,
    structlog.processors.JSONRenderer(),
]

_CONSOLE_PROCESSORS: list[Any] = [
    *_SHARED_PROCESSORS,
    structlog.dev.ConsoleRenderer(colors=True),
]







def setup_logging(settings: AppSettings | None = None) -> None:
    if settings is None:
        settings = get_settings()

    log_level_int = getattr(logging, settings.log_level, logging.INFO)




    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level_int,
        force=True,
    )


    if settings.log_level != "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


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







def get_logger(name: str | None = None) -> FilteringBoundLogger:
    return structlog.get_logger(name)







def bind_request_context(
    request_id: str,
    *,
    endpoint: str | None = None,
    client_ip: str | None = None,
) -> None:
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
    ctx: dict[str, Any] = {"claim_id": claim_id}
    if stage_id:
        ctx["stage_id"] = stage_id
    if normalized_source:
        ctx["normalized_source"] = normalized_source
    structlog.contextvars.bind_contextvars(**ctx)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()
