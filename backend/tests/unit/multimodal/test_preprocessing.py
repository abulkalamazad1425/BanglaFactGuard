"""The evaluation transform must match training: resize, then ImageNet normalisation."""

import torch
from PIL import Image

from app.features.multimodal.pipeline.preprocessing import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    build_eval_transform,
)


def test_images_are_resized_and_imagenet_normalised():
    tensor = build_eval_transform(16)(Image.new("RGB", (40, 20), (255, 255, 255)))
    assert tensor.shape == (3, 16, 16)
    expected = torch.tensor([(1 - m) / s for m, s in zip(IMAGENET_MEAN, IMAGENET_STD, strict=True)])
    assert torch.allclose(tensor[:, 0, 0], expected, atol=1e-5)
