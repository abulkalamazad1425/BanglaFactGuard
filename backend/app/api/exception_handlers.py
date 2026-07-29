from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import BanglaFactGuardError

logger = structlog.get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(BanglaFactGuardError)
    async def domain_error_handler(
        request: Request, exc: BanglaFactGuardError
    ) -> JSONResponse:
        logger.warning(
            "domain_error",
            path=str(request.url),
            error_type=type(exc).__name__,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status_code,
            content={
                "error": type(exc).__name__,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            path=str(request.url),
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred.",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
