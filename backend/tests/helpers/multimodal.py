"""A tiny stand-in for the loaded BanglaBERT + EfficientNet weights: real
tensors and real preprocessing, but a few deterministic numbers instead of
the trained networks. Says nothing about the trained model's accuracy."""

from __future__ import annotations

import io

import torch
from PIL import Image


class TinyLoader:
    is_loaded = True
    device = torch.device("cpu")

    def __init__(self, logits=(0.0, 2.0)) -> None:
        self.logits = torch.tensor([list(logits)])
        self.classifier_inputs: list = []

    @staticmethod
    def tokenizer(text, **kw):
        ids = torch.tensor([[len(text) % 7, 1, 2, 0]])
        return {"input_ids": ids, "attention_mask": torch.ones_like(ids)}

    @staticmethod
    def text_backbone(input_ids, attention_mask):
        return torch.cat([input_ids.float(), attention_mask.float()], dim=1)  # (1, 8)

    @staticmethod
    def img_backbone(images):
        return images.mean(dim=(2, 3))  # (1, 3): per-channel mean

    def classifier(self, img_feats, text_feats):
        self.classifier_inputs.append((img_feats.clone(), text_feats.clone()))
        return self.logits


def png(color=(255, 0, 0), size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()
