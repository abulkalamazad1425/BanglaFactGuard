from __future__ import annotations

import pytest

from tests.helpers.db import make_session_factory


@pytest.fixture
async def db():
    engine, factory = await make_session_factory()
    yield factory
    await engine.dispose()


@pytest.fixture
async def session(db):
    async with db() as s:
        yield s


@pytest.fixture
async def file_db(tmp_path):
    engine, factory = await make_session_factory(str(tmp_path / "test.db"))
    yield factory
    await engine.dispose()
