"""
app/features/multimodal/pipeline/model_architecture.py
=======================================================
PyTorch module definitions for the BanglaBERT + EfficientNet-B4 multimodal
fake-news classifier.

IMPORTANT: These class definitions are an exact replica of the training-time
definitions in ``MultiBanFake_BanglaBERT_EfficientNetB4.ipynb``. Any change
here will break checkpoint loading. Do not modify unless you are also
retraining the model.

Architecture summary:
    EfficientNetBackbone  — timm EfficientNet-B4 without the classifier head
                            Output: [B, 1792]
    BanglaBERTBackbone    — csebuetnlp/banglabert; returns [CLS] token embedding
                            Output: [B, 768]
    MultiFusionFake       — LayerNorm(2560) → Linear(1024) → GELU → Dropout
                            → Linear(512) → GELU → Dropout → Linear(2)
                            Output: [B, 2] logits

Label mapping: 0 = NON_FAKE (Real),  1 = FAKE
"""

from __future__ import annotations

import torch
import torch.nn as nn
import timm
from transformers import AutoModel


class EfficientNetBackbone(nn.Module):
    """EfficientNet-B4 without the final classifier head.

    Args:
        model_name: timm model identifier (default: ``'efficientnet_b4'``).
        pretrained:  Whether to load ImageNet pre-trained weights when
                     constructing the backbone. Set ``False`` when loading
                     fine-tuned weights from a checkpoint file.
    """

    def __init__(self, model_name: str = "efficientnet_b4", pretrained: bool = True) -> None:
        super().__init__()
        self.backbone = timm.create_model(
            model_name,
            pretrained=pretrained,
            num_classes=0,      # Remove classifier head
            global_pool="avg",  # Global average pooling → single feature vector
        )
        self.out_dim: int = self.backbone.num_features  # 1792 for B4

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Image tensor [B, 3, H, W]
        Returns:
            Feature vector [B, 1792]
        """
        return self.backbone(x)


class BanglaBERTBackbone(nn.Module):
    """BanglaBERT text encoder — returns the [CLS] token embedding.

    Args:
        model_name: HuggingFace model identifier.
    """

    def __init__(self, model_name: str = "csebuetnlp/banglabert") -> None:
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.out_dim: int = self.bert.config.hidden_size  # 768

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            input_ids:      Token ids [B, max_seq_length]
            attention_mask: Padding mask [B, max_seq_length]
        Returns:
            [CLS] embedding [B, 768]
        """
        out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        return out.last_hidden_state[:, 0, :]  # [CLS] token


class MultiFusionFake(nn.Module):
    """
    Early-fusion multimodal classifier.

    Concatenates EfficientNet-B4 and BanglaBERT features, applies LayerNorm,
    then classifies via a two-layer MLP with GELU activations.

    Args:
        img_dim:     Output dimension of the image backbone (1792 for B4).
        text_dim:    Output dimension of the text backbone (768 for BanglaBERT).
        num_classes: Number of output classes (2: FAKE / NON_FAKE).
        dropout:     Dropout probability applied after each hidden layer.
    """

    def __init__(
        self,
        img_dim: int,
        text_dim: int,
        num_classes: int,
        dropout: float = 0.4,
    ) -> None:
        super().__init__()
        fused_dim = img_dim + text_dim  # 1792 + 768 = 2560

        self.norm = nn.LayerNorm(fused_dim)

        self.classifier = nn.Sequential(
            nn.Linear(fused_dim, 1024),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(1024, 512),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(512, num_classes),
        )

    def forward(
        self,
        img_feats: torch.Tensor,
        text_feats: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            img_feats:  Image features [B, 1792]
            text_feats: Text [CLS] features [B, 768]
        Returns:
            Logits [B, 2]
        """
        fused = torch.cat([img_feats, text_feats], dim=-1)  # [B, 2560]
        fused = self.norm(fused)
        return self.classifier(fused)
