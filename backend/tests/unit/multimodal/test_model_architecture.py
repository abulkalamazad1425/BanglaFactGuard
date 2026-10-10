"""Shapes the trained checkpoints depend on: image features + text [CLS]
features are fused and classified. Small configs, random weights."""

import torch
from transformers import BertConfig, BertModel

from app.features.multimodal.pipeline import model_architecture as arch


def test_backbones_expose_their_feature_size_and_the_classifier_fuses_both(monkeypatch):
    image = arch.EfficientNetBackbone("efficientnet_b0", pretrained=False).eval()
    assert image(torch.zeros(1, 3, 32, 32)).shape == (1, image.out_dim)

    tiny_bert = BertModel(BertConfig(hidden_size=8, num_hidden_layers=1, num_attention_heads=2, intermediate_size=16,
                                     vocab_size=50))
    monkeypatch.setattr(arch.AutoModel, "from_pretrained", staticmethod(lambda name: tiny_bert))
    text = arch.BanglaBERTBackbone("csebuetnlp/banglabert").eval()
    ids = torch.tensor([[1, 2, 3]])
    assert text.out_dim == 8 and text(ids, torch.ones_like(ids)).shape == (1, 8)  # the [CLS] vector

    logits = arch.MultiFusionFake(img_dim=image.out_dim, text_dim=8, num_classes=2).eval()(
        torch.zeros(1, image.out_dim), torch.zeros(1, 8)
    )
    assert logits.shape == (1, 2)
