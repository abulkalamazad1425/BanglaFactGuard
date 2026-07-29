from __future__ import annotations

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import CorrelationIDMiddleware, ProcessTimeMiddleware
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.lifespan import lifespan

_SETTINGS = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="BanglaFactGuard",
        summary="Multimodal Bangla Source-Based Fact Verification API",
        description=(
            "Given a news article and a claimed source, BanglaFactGuard determines "
            "whether that source actually published the article using a 12-stage "
            "verification pipeline combining search, NLU, NER, and NLI."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_SETTINGS.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.add_middleware(ProcessTimeMiddleware)
    app.add_middleware(CorrelationIDMiddleware)

    app.include_router(api_router)

    register_exception_handlers(app)

    return app


app = create_app()
