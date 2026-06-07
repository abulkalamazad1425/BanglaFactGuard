"""
app/api/middleware.py
======================
FastAPI middleware stack for BanglaFactGuard.

Middleware applied (in order — outermost first):
1. CorrelationIDMiddleware  — injects X-Request-ID into every request/response.
2. ProcessTimeMiddleware    — adds X-Process-Time-Ms response header.
3. RateLimitMiddleware      — per-IP token-bucket rate limiting via Redis.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Inject a correlation / request ID into every request.

    If the client sends `X-Request-ID`, it is used as-is.
    Otherwise a new UUID4 is generated. The ID is added to every response
    header so clients can correlate logs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    """
    Add X-Process-Time-Ms header to every response.

    Records wall-clock time from the moment the request enters the middleware
    to the moment the response is dispatched. Useful for monitoring p99 latencies
    without deploying a full APM agent.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        return response
