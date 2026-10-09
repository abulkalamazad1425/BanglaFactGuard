"""Loaded state belongs to the loader instance that holds the weights."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ModelNotLoadedError
from app.features.multimodal.pipeline.model_loader import MultimodalModelLoader


def _fake_weights():
    img, text = MagicMock(out_dim=1792), MagicMock(out_dim=768)
    return img, text, MagicMock(), MagicMock()


@pytest.mark.asyncio
async def test_a_new_loader_does_not_inherit_another_instances_loaded_state():
    first = MultimodalModelLoader()
    with (
        patch.object(MultimodalModelLoader, "_validate_model_dir"),
        patch.object(MultimodalModelLoader, "_load_sync", return_value=_fake_weights()),
    ):
        await first.load()
    assert first.is_loaded
    assert first.img_backbone.out_dim == 1792

    second = MultimodalModelLoader()
    assert second.is_loaded is False
    with pytest.raises(ModelNotLoadedError):
        _ = second.img_backbone


@pytest.mark.asyncio
async def test_load_is_idempotent_per_instance():
    loader = MultimodalModelLoader()
    with (
        patch.object(MultimodalModelLoader, "_validate_model_dir"),
        patch.object(MultimodalModelLoader, "_load_sync", return_value=_fake_weights()) as load_sync,
    ):
        await loader.load()
        await loader.load()
    assert load_sync.call_count == 1
