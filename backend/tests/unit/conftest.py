from __future__ import annotations

import pytest

from tests.helpers.db import make_session_factory


@pytest.fixture
async def db():
    """Session factory over a fresh in-memory database."""
    engine, factory = await make_session_factory()
    yield factory
    await engine.dispose()


@pytest.fixture
async def session(db):
    async with db() as s:
        yield s


@pytest.fixture
async def file_db(tmp_path):
    """Session factory over a file database, for code that opens its own
    sessions concurrently with the test (background workers)."""
    engine, factory = await make_session_factory(str(tmp_path / "test.db"))
    yield factory
    await engine.dispose()
