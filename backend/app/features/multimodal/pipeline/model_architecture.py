from __future__ import annotations

import torch
import torch.nn as nn
import timm
from transformers import AutoModel


class EfficientNetBackbone(nn.Module):

    def __init__(
        self, model_name: str = "efficientnet_b4", pretrained: bool = True
    ) -> None:
        super().__init__()
        self.backbone = timm.create_model(
            model_name,
            pretrained=pretrained,
            num_classes=0,
            global_pool="avg",
        )
        self.out_dim: int = self.backbone.num_features

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)


class BanglaBERTBackbone(nn.Module):

    def __init__(self, model_name: str = "csebuetnlp/banglabert") -> None:
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.out_dim: int = self.bert.config.hidden_size

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        return out.last_hidden_state[:, 0, :]


class MultiFusionFake(nn.Module):

    def __init__(
        self,
        img_dim: int,
        text_dim: int,
        num_classes: int,
        dropout: float = 0.4,
    ) -> None:
        super().__init__()
        fused_dim = img_dim + text_dim

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
        fused = torch.cat([img_feats, text_feats], dim=-1)
        fused = self.norm(fused)
        return self.classifier(fused)
