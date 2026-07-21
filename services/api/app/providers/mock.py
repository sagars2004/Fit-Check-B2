from __future__ import annotations

import hashlib
from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageDraw

from app.providers.contracts import GeneratedMedia, ImageGenerationRequest


class MockMediaOrchestrator:
    """Offline deterministic stand-in for a paid GMI image generation run."""

    async def generate_image(self, request: ImageGenerationRequest) -> GeneratedMedia:
        seed = hashlib.sha256(f"{request.garment_id}:{request.prompt}".encode()).digest()
        fill = (30 + seed[0] % 60, 45 + seed[1] % 75, 70 + seed[2] % 90, 255)
        accent = (120 + seed[3] % 90, 130 + seed[4] % 80, 145 + seed[5] % 70, 255)
        canvas = Image.new("RGBA", (512, 640), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        # A deliberately generic garment silhouette: it is labeled as reconstructed, never verified.
        draw.rounded_rectangle((150, 150, 362, 525), radius=28, fill=fill)
        draw.polygon(((150, 175), (78, 255), (112, 340), (175, 300)), fill=fill)
        draw.polygon(((362, 175), (434, 255), (400, 340), (337, 300)), fill=fill)
        draw.polygon(((212, 150), (256, 205), (300, 150)), fill=accent)
        for y in range(250, 500, 52):
            draw.line((176, y, 336, y), fill=accent, width=4)
        output = BytesIO()
        canvas.save(output, format="PNG")
        run_id = f"mock-{uuid4()}"
        return GeneratedMedia(
            run_id=run_id,
            provider="mock",
            model="fit-check-local-mock-v1",
            content=output.getvalue(),
            content_type="image/png",
            provider_manifest={"mode": "offline", "deterministic_seed": seed.hex()[:16]},
        )

