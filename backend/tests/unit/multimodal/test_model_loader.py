"""Weights load once per loader instance, from a complete model directory,
into eval-mode modules; nothing is reported loaded that is not."""

from __future__ import annotations

import os

import pytest
import torch
from torch import nn

from app.core.exceptions import InferenceError, ModelNotLoadedError
from app.features.multimodal.pipeline import model_loader as module
from app.features.multimodal.pipeline.model_loader import MultimodalModelLoader


class Tiny(nn.Module):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.layer = nn.Linear(2, 2)
        self.out_dim = 2


@pytest.fixture
def model_dir(tmp_path, monkeypatch):
    for name in ("img_backbone.pt", "text_backbone.pt", "classifier.pt"):
        weights = Tiny().state_dict()
        weights["layer.bias"] = torch.full((2,), 7.0)
        torch.save(weights, tmp_path / name)
    (tmp_path / "tokenizer").mkdir()
    for cls in ("EfficientNetBackbone", "BanglaBERTBackbone", "MultiFusionFake"):
        monkeypatch.setattr(module, cls, Tiny)
    monkeypatch.setattr(module.AutoTokenizer, "from_pretrained", staticmethod(lambda path: f"tokenizer@{os.path.basename(path)}"))
    monkeypatch.setattr(module._SETTINGS.multimodal, "model_dir", str(tmp_path))
    return tmp_path


async def test_weights_load_into_eval_mode_once_per_instance(model_dir):
    loader = MultimodalModelLoader()
    with pytest.raises(ModelNotLoadedError):
        _ = loader.classifier
    await loader.load()
    await loader.load()
    assert loader.is_loaded and loader.tokenizer == "tokenizer@tokenizer"
    for part in (loader.img_backbone, loader.text_backbone, loader.classifier):
        assert not part.training and part.layer.bias.tolist() == [7.0, 7.0]
    fresh = MultimodalModelLoader()  # a later startup does not inherit this instance's state
    assert fresh.is_loaded is False and str(fresh.device) == "cpu"
    for prop in ("img_backbone", "text_backbone", "tokenizer"):
        with pytest.raises(ModelNotLoadedError):
            getattr(fresh, prop)


async def test_a_missing_or_broken_model_directory_is_an_inference_error(model_dir):
    os.remove(model_dir / "classifier.pt")
    with pytest.raises(InferenceError, match="classifier.pt"):
        await MultimodalModelLoader().load()
    torch.save({"wrong": torch.zeros(1)}, model_dir / "classifier.pt")
    loader = MultimodalModelLoader()
    with pytest.raises(InferenceError, match="Weight loading failed"):
        await loader.load()
    assert not loader.is_loaded
