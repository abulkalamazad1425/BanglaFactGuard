"""Image preprocessing shared by the embedding extractor and the inference
engine. Must match the training-time evaluation transform."""

from __future__ import annotations

from torchvision import transforms

# ImageNet normalisation used by the EfficientNet backbone during training.
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_eval_transform(img_size: int) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )
