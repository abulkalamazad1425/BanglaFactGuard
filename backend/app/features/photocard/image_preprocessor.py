"""
Image preparation for Bangla photo-card OCR.

Photo cards are screenshots and social-media graphics, not scans: the text is
already crisp but often small, tightly kerned, and frequently light-on-dark
over a photographic background. Bangla makes this harder than Latin because
the matra (the connecting headline stroke) merges adjacent glyphs whenever the
image is downscaled or JPEG-blurred, and OCR then reads a whole word as one
unrecognised blob.

Rather than guess a single "best" preprocessing recipe, this module renders a
handful of cheap variants and lets the OCR service score them by how much
Bangla it could actually read. That costs a few hundred milliseconds and buys
a large accuracy gain on real-world cards.

Everything here is Pillow + NumPy only — no OpenCV dependency.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from app.core.config import get_settings

_SETTINGS = get_settings()


@dataclass(frozen=True)
class ImageVariant:
    """One rendered candidate handed to the OCR engine."""

    name: str
    image: Image.Image


def load_image(image_bytes: bytes) -> Image.Image:
    """Decode upload bytes into an orientation-corrected RGB image."""
    image = Image.open(io.BytesIO(image_bytes))
    # Phone screenshots carry EXIF rotation; OCR on a sideways card returns junk.
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def build_variants(image_bytes: bytes) -> list[ImageVariant]:
    """Render the preprocessing variants tried during recognition.

    Returns between three and four variants, cheapest first:

    ``grayscale``   resized + contrast-stretched greyscale — the safe baseline.
    ``sharpened``   unsharp mask, which re-separates matra-merged glyphs.
    ``binarised``   Otsu threshold, which helps flat-background cards a lot and
                    hurts photographic ones (hence: a candidate, not the rule).
    ``inverted``    only for light-on-dark cards, where every engine trained on
                    dark-on-light text otherwise reads nothing at all.
    """
    base = load_image(image_bytes)
    base = _rescale(base)

    grayscale = ImageOps.autocontrast(base.convert("L"), cutoff=1)

    sharpened = grayscale.filter(
        ImageFilter.UnsharpMask(radius=2.0, percent=180, threshold=2)
    )

    binarised = _otsu_binarise(sharpened)

    variants = [
        ImageVariant("grayscale", grayscale),
        ImageVariant("sharpened", sharpened),
        ImageVariant("binarised", binarised),
    ]

    if _is_light_on_dark(grayscale):
        variants.append(ImageVariant("inverted", ImageOps.invert(sharpened)))

    return variants


def _rescale(image: Image.Image) -> Image.Image:
    """Bring the image into the resolution band where OCR engines perform best.

    Small cards are upscaled (LANCZOS keeps the matra continuous), oversized
    ones are downscaled so recognition does not blow up in time and memory.
    """
    width, height = image.size
    if width == 0 or height == 0:
        return image

    min_width = _SETTINGS.ocr.upscale_min_width
    max_dim = _SETTINGS.ocr.max_dimension

    scale = 1.0
    if width < min_width:
        scale = min_width / width
    longest = max(width, height) * scale
    if longest > max_dim:
        scale *= max_dim / longest

    if abs(scale - 1.0) < 0.01:
        return image

    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    resample = Image.LANCZOS if scale > 1.0 else Image.BICUBIC
    return image.resize(new_size, resample)


def _otsu_binarise(gray: Image.Image) -> Image.Image:
    """Binarise using Otsu's method computed from the 256-bin histogram."""
    histogram = np.asarray(gray.histogram()[:256], dtype=np.float64)
    total = histogram.sum()
    if total == 0:
        return gray

    levels = np.arange(256, dtype=np.float64)
    weight_bg = np.cumsum(histogram)
    weight_fg = total - weight_bg

    cumulative_mean = np.cumsum(histogram * levels)
    grand_mean = cumulative_mean[-1]

    # Guard the empty-class ends where the between-class variance is undefined.
    valid = (weight_bg > 0) & (weight_fg > 0)
    if not valid.any():
        return gray

    mean_bg = np.divide(
        cumulative_mean, weight_bg, out=np.zeros_like(cumulative_mean), where=weight_bg > 0
    )
    mean_fg = np.divide(
        grand_mean - cumulative_mean,
        weight_fg,
        out=np.zeros_like(cumulative_mean),
        where=weight_fg > 0,
    )
    between_variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
    between_variance[~valid] = -1.0

    threshold = int(np.argmax(between_variance))
    return gray.point(lambda px, t=threshold: 255 if px > t else 0, mode="L")


def _is_light_on_dark(gray: Image.Image) -> bool:
    """Detect cards whose text is light on a dark background.

    Sampling the border rather than the whole frame: photo cards put their
    background colour at the edges, while the centre is dominated by the text
    block itself.
    """
    array = np.asarray(gray, dtype=np.float32)
    if array.size == 0:
        return False

    border = min(max(array.shape[0] // 10, 1), array.shape[0])
    edges = np.concatenate(
        [
            array[:border, :].ravel(),
            array[-border:, :].ravel(),
            array[:, :border].ravel(),
            array[:, -border:].ravel(),
        ]
    )
    return bool(edges.mean() < 110.0)
