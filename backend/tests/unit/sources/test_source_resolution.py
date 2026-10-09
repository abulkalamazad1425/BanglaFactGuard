"""Claimed-source text -> canonical domain: URL, then static alias, then the
registry; None (never a guess) when all three miss."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.sources.resolution import resolve_claimed_source


def repo(found=None, *, error=False) -> AsyncMock:
    r = AsyncMock()
    r.resolve_source.side_effect = RuntimeError("db unreachable") if error else None
    r.resolve_source.return_value = MagicMock(canonical_name=found) if found else None
    return r


@pytest.mark.parametrize("raw,registry,expected,looked_up", [
    ("https://www.prothomalo.com/some/path", None, "prothomalo.com", False),   # URL wins, no DB call
    ("প্রথম আলো", None, "prothomalo.com", False),                             # static alias
    ("এক্সাম্পল নিউজ", "example-news.com", "example-news.com", True),          # registry
    ("কোনো অজানা পত্রিকা", None, None, True),
    ("", None, None, False),
])
async def test_resolution_order(raw, registry, expected, looked_up):
    r = repo(registry)
    assert await resolve_claimed_source(raw, r) == expected
    assert r.resolve_source.await_count == int(looked_up)


async def test_a_registry_failure_is_unresolved_not_an_error():
    assert await resolve_claimed_source("কোনো পত্রিকা", repo(error=True)) is None
