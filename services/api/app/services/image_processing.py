from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import cast

from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError

from app.core.errors import FitCheckError


@dataclass(frozen=True, slots=True)
class ImageQaResult:
    passed: bool
    warnings: tuple[str, ...]
    width: int
    height: int
    transparent_corner_count: int
    alpha_bbox: tuple[int, int, int, int] | None


@dataclass(frozen=True, slots=True)
class ImageInspection:
    width: int
    height: int
    image_format: str
    content_type: str


_SUPPORTED_IMAGE_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def inspect_upload_image(source: bytes) -> ImageInspection:
    """Decode and identify a user image before durable processing.

    Pillow performs the file-signature/decode check here, so a client supplied
    MIME type is never accepted as proof that an upload is usable.
    """

    try:
        with Image.open(BytesIO(source)) as image:
            image.load()
            normalized = ImageOps.exif_transpose(image)
            image_format = image.format or ""
            content_type = _SUPPORTED_IMAGE_FORMATS.get(image_format)
            if content_type is None:
                raise FitCheckError(
                    "UNSUPPORTED_IMAGE",
                    "Use a JPG, PNG, or WebP outfit photo. HEIC can be converted before upload.",
                    recommended_action="Choose a supported image or export the photo as JPG.",
                )
            return ImageInspection(
                width=normalized.width,
                height=normalized.height,
                image_format=image_format,
                content_type=content_type,
            )
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise FitCheckError(
            "INVALID_IMAGE",
            "This photo could not be decoded safely.",
            recommended_action="Choose a different JPG, PNG, or WebP photo and try again.",
        ) from error


def normalize_image(source: bytes, *, output_format: str = "JPEG") -> bytes:
    """Normalize EXIF orientation deterministically without generative processing."""
    with Image.open(BytesIO(source)) as image:
        normalized = ImageOps.exif_transpose(image)
        if output_format.upper() == "JPEG":
            if normalized.mode not in {"RGB", "L"}:
                normalized = normalized.convert("RGB")
        else:
            normalized = normalized.convert("RGBA")
        output = BytesIO()
        normalized.save(output, format=output_format, quality=92, optimize=True)
        return output.getvalue()


def crop_normalized_image(source: bytes, *, left: int, top: int, right: int, bottom: int) -> bytes:
    """Create a deterministic JPEG source crop for review, never a cutout."""

    with Image.open(BytesIO(source)) as image:
        normalized = ImageOps.exif_transpose(image).convert("RGB")
        bounded_left = max(0, min(left, normalized.width - 1))
        bounded_top = max(0, min(top, normalized.height - 1))
        bounded_right = max(bounded_left + 1, min(right, normalized.width))
        bounded_bottom = max(bounded_top + 1, min(bottom, normalized.height))
        crop = normalized.crop((bounded_left, bounded_top, bounded_right, bounded_bottom))
        output = BytesIO()
        crop.save(output, format="JPEG", quality=92, optimize=True)
        return output.getvalue()


def approximate_color_name(source: bytes) -> str:
    """Return a deliberately coarse, deterministic color label for review."""

    palette = {
        "black": (30, 30, 30),
        "white": (235, 235, 230),
        "gray": (125, 125, 125),
        "navy": (34, 55, 92),
        "blue": (65, 120, 200),
        "green": (68, 126, 83),
        "red": (180, 68, 64),
        "brown": (118, 82, 55),
        "beige": (202, 181, 145),
    }
    with Image.open(BytesIO(source)) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB").resize((1, 1))
        red, green, blue = cast(tuple[int, int, int], rgb.getpixel((0, 0)))
    return min(
        palette,
        key=lambda name: sum(
            (component - target) ** 2
            for component, target in zip((red, green, blue), palette[name], strict=True)
        ),
    )


def chroma_to_transparent(source: bytes, *, green_bias: int = 32) -> bytes:
    """Remove a known chroma-green background deterministically."""
    with Image.open(BytesIO(source)).convert("RGBA") as image:
        pixels = image.load()
        for y in range(image.height):
            for x in range(image.width):
                red, green, blue, alpha = pixels[x, y]
                if green > red + green_bias and green > blue + green_bias:
                    pixels[x, y] = (red, green, blue, 0)
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


def validate_cutout_png(source: bytes) -> ImageQaResult:
    warnings: list[str] = []
    with Image.open(BytesIO(source)) as image:
        if image.format != "PNG":
            warnings.append("not_png")
        if image.mode != "RGBA":
            warnings.append("not_rgba")
            rgba = image.convert("RGBA")
        else:
            rgba = image
        alpha = rgba.getchannel("A")
        bbox = alpha.getbbox()
        if bbox is None:
            warnings.append("empty_alpha")
        corners = [
            alpha.getpixel((0, 0)),
            alpha.getpixel((rgba.width - 1, 0)),
            alpha.getpixel((0, rgba.height - 1)),
            alpha.getpixel((rgba.width - 1, rgba.height - 1)),
        ]
        transparent_corners = sum(pixel == 0 for pixel in corners)
        if transparent_corners < 4:
            warnings.append("opaque_corners")
        if bbox is not None:
            left, top, right, bottom = bbox
            if left == 0 or top == 0 or right == rgba.width or bottom == rgba.height:
                warnings.append("clipped_extremity")
            if (right - left) < max(16, rgba.width // 20) or (bottom - top) < max(
                16, rgba.height // 20
            ):
                warnings.append("subject_too_small")
        return ImageQaResult(
            passed=not warnings,
            warnings=tuple(warnings),
            width=rgba.width,
            height=rgba.height,
            transparent_corner_count=transparent_corners,
            alpha_bbox=bbox,
        )


def perceptual_input_fingerprint(source: bytes) -> str:
    """A stable, cheap local fingerprint for coarse duplicate ranking."""

    return hashlib.sha256(perceptual_bit_signature(source).encode("ascii")).hexdigest()


def perceptual_bit_signature(source: bytes) -> str:
    """Return a local luma signature suitable for review-only ranking."""

    with Image.open(BytesIO(source)) as image:
        grayscale = ImageOps.exif_transpose(image).convert("L").resize((16, 16))
        pixels = grayscale.tobytes()
        average = sum(pixels) / len(pixels)
        return "".join("1" if pixel >= average else "0" for pixel in pixels)


def perceptual_similarity(left: str, right: str) -> float:
    """Fraction of matching signature bits; never a merge decision."""

    if not left or len(left) != len(right):
        return 0.0
    return sum(a == b for a, b in zip(left, right, strict=True)) / len(left)


def alpha_content_bbox(source: bytes) -> tuple[int, int, int, int] | None:
    with Image.open(BytesIO(source)).convert("RGBA") as image:
        return ImageChops.difference(image.getchannel("A"), Image.new("L", image.size)).getbbox()
