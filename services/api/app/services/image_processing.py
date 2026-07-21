from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageChops, ImageOps


@dataclass(frozen=True, slots=True)
class ImageQaResult:
    passed: bool
    warnings: tuple[str, ...]
    width: int
    height: int
    transparent_corner_count: int
    alpha_bbox: tuple[int, int, int, int] | None


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
    with Image.open(BytesIO(source)) as image:
        grayscale = ImageOps.exif_transpose(image).convert("L").resize((16, 16))
        pixels = grayscale.tobytes()
        average = sum(pixels) / len(pixels)
        bits = "".join("1" if pixel >= average else "0" for pixel in pixels)
        return hashlib.sha256(bits.encode("ascii")).hexdigest()


def alpha_content_bbox(source: bytes) -> tuple[int, int, int, int] | None:
    with Image.open(BytesIO(source)).convert("RGBA") as image:
        return ImageChops.difference(image.getchannel("A"), Image.new("L", image.size)).getbbox()
