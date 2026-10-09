from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)


_settings = get_settings()


_async_engine: AsyncEngine = create_async_engine(
    url=_settings.db.async_url,
    echo=_settings.db.echo_sql,
    pool_size=_settings.db.pool_size,
    max_overflow=_settings.db.max_overflow,
    pool_timeout=_settings.db.pool_timeout,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={"server_settings": {"jit": "off"}},
)


AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


def get_engine() -> AsyncEngine:
    return _async_engine


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
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


async def close_engine() -> None:
    await _async_engine.dispose()
    logger.info("Database engine pool disposed.")
