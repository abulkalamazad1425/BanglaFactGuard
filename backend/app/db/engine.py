"""
app/db/engine.py
================
Async SQLAlchemy 2.0 engine, session factory, and dependency helpers.

Design decisions:
- `create_async_engine` with `asyncpg` driver is used throughout; Alembic
  uses a separate sync engine (psycopg2) only during migrations.
- `async_sessionmaker` (SQLAlchemy 2.0 API) replaces the older
  `sessionmaker` — it returns `AsyncSession` instances directly and
  supports `expire_on_commit=False` which is critical for async code
  (expired attributes cannot be lazily loaded outside a session).
- The engine is created once at module import and shared across all
  requests via the FastAPI dependency `get_async_session`.
- `get_async_session` is an async generator that yields a session and
  guarantees rollback on exception + close on completion — even if the
  caller raises.
- `check_db_connection` is a lightweight healthcheck helper called during
  the FastAPI lifespan startup to fail fast if the DB is unreachable.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons — created once on first import
# ---------------------------------------------------------------------------

_settings = get_settings()

# Async engine — used by the application
_async_engine: AsyncEngine = create_async_engine(
    url=_settings.db.async_url,
    echo=_settings.db.echo_sql,
    pool_size=_settings.db.pool_size,
    max_overflow=_settings.db.max_overflow,
    pool_timeout=_settings.db.pool_timeout,
    # Return connection to pool after 30 min of inactivity
    pool_recycle=1800,
    # Pre-ping avoids "connection already closed" errors after DB restart
    pool_pre_ping=True,
    # asyncpg-specific: enable native UUID type support
    connect_args={"server_settings": {"jit": "off"}},
)

# Session factory — call `AsyncSessionLocal()` to get a new session
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,   # Required for async: prevents lazy-load after commit
    autoflush=False,          # Explicit flush control for better performance
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Engine accessors
# ---------------------------------------------------------------------------


def get_engine() -> AsyncEngine:
    """
    Return the shared async SQLAlchemy engine.

    Primarily used by Alembic's async migration runner and test fixtures
    that need direct engine access to create/drop tables.
    """
    return _async_engine


# ---------------------------------------------------------------------------
# Session dependency (FastAPI)
# ---------------------------------------------------------------------------


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.

    Guarantees:
    - Session is always closed after the request completes.
    - On unhandled exception, the transaction is rolled back before closing.

    Usage in endpoints::

        from app.db.engine import get_async_session
        from sqlalchemy.ext.asyncio import AsyncSession
        from fastapi import Depends

        @router.post("/verify")
        async def verify(db: AsyncSession = Depends(get_async_session)):
            ...

    Usage via repository DI (preferred)::

        from app.api.dependencies import get_claim_repository

        @router.post("/verify")
        async def verify(repo = Depends(get_claim_repository)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error(
                "Database session error — rolled back",
                exc_info=exc,
                extra={"error_type": type(exc).__name__},
            )
            raise
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Context-manager session (for use outside of FastAPI DI, e.g. workers)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for obtaining a session outside of FastAPI's
    dependency injection (e.g. background workers, CLI scripts, tests).

    Usage::

        async with get_db_context() as db:
            result = await db.execute(select(VerifiedClaim))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error(
                "Database context manager error — rolled back",
                exc_info=exc,
            )
            raise
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


async def check_db_connection() -> None:
    """
    Execute a trivial query to verify the database is reachable.

    Called during FastAPI lifespan startup. Raises `ConfigurationError`
    if the connection cannot be established, which prevents the server
    from starting with a broken DB.

    Raises:
        ConfigurationError: If the database is unreachable.
    """
    try:
        async with _async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully.")
    except Exception as exc:
        raise ConfigurationError(
            message="Cannot connect to PostgreSQL. Check DB_* environment variables.",
            details={"error": str(exc), "url": _settings.db.async_url},
        ) from exc


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------


async def close_engine() -> None:
    """
    Dispose of all connections in the async engine pool.

    Called during FastAPI lifespan shutdown to ensure graceful connection
    release without waiting for the OS to close sockets.
    """
    await _async_engine.dispose()
    logger.info("Database engine pool disposed.")
