"""LaBSE wrapper: loads once, caches vectors by text, clips similarity to [0, 1].
A fake model is used; nothing here measures LaBSE itself."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.features.nlp import embedding_service as module
from app.features.nlp.embedding_service import EmbeddingService


class FakeModel:
    def __init__(self, name, **kw):
        self.name, self.calls = name, []

    def encode(self, texts, **kw):
        self.calls.append(texts)
        vec = lambda t: np.array([1.0, 0.0]) if "a" in t else np.array([-1.0, 0.0])  # noqa: E731
        return np.array([vec(t) for t in texts]) if isinstance(texts, list) else vec(texts)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(EmbeddingService, "_model", None)
    monkeypatch.setattr(EmbeddingService, "_loaded", False)
    monkeypatch.setattr(module, "SentenceTransformer", FakeModel)


def cache(cached=None, *, broken=False) -> MagicMock:
    return MagicMock(get_raw=AsyncMock(side_effect=RuntimeError("redis") if broken else None, return_value=cached),
                     set_raw=AsyncMock())


async def test_nothing_is_encoded_before_the_model_loads_and_it_loads_once(monkeypatch):
    svc = EmbeddingService(cache())
    with pytest.raises(RuntimeError):
        await svc.encode("a")
    with pytest.raises(RuntimeError):
        await svc.encode_batch(["a"])
    monkeypatch.setattr(module._SETTINGS.ml, "embedding_model_name", module.LEGACY_EMBEDDING_SETTING)
    await svc.load()
    first = EmbeddingService._model
    await svc.load()
    assert EmbeddingService._model is first and first.name == "sentence-transformers/LaBSE"


async def test_a_failed_load_is_raised_and_leaves_the_service_unloaded(monkeypatch):
    def broken(*a, **k):
        raise OSError("no weights")

    monkeypatch.setattr(module, "SentenceTransformer", broken)
    with pytest.raises(OSError):
        await EmbeddingService(cache()).load()
    assert EmbeddingService._loaded is False


async def test_vectors_are_cached_by_text_and_cache_trouble_is_ignored():
    hit = EmbeddingService(cache(json.dumps([0.5, 0.5]).encode()))
    await hit.load()
    assert hit_vector(await hit.encode("a")) == [0.5, 0.5] and EmbeddingService._model.calls == []

    miss_cache = cache()
    miss = EmbeddingService(miss_cache)
    assert hit_vector(await miss.encode("a")) == [1.0, 0.0]
    await asyncio.sleep(0)  # the cache write runs in the background
    key, payload = miss_cache.set_raw.await_args.args
    assert key.startswith(module._CACHE_KEY_PREFIX) and json.loads(payload) == [1.0, 0.0]

    assert hit_vector(await EmbeddingService(cache(broken=True)).encode("a")) == [1.0, 0.0]


async def test_similarity_is_clipped_and_batches_are_encoded_together():
    svc = EmbeddingService(cache())
    await svc.load()
    assert await svc.compute_similarity("a", "a") == 1.0
    assert await svc.compute_similarity("a", "b") == 0.0  # raw cosine -1 is shown as 0
    vectors = await svc.encode_batch(["a", "b"])
    assert [hit_vector(v) for v in vectors] == [[1.0, 0.0], [-1.0, 0.0]]


def hit_vector(v) -> list[float]:
    return [round(float(x), 4) for x in v]
