from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import httpx

from app.core.config import Settings


@dataclass
class DetectedGarment:
    name_suggestion: str
    category: str
    colors: list[str]
    bbox: dict[str, float]  # left, top, right, bottom
    apparent_material: str
    pattern: str
    confidence: float
    unresolved_details: list[str]


async def extract_garments_with_vision(
    image_bytes: bytes,
    width: int,
    height: int,
    settings: Settings,
) -> list[DetectedGarment]:
    """Call GMI multimodal vision model if configured, or return fallback candidate."""

    if not settings.has_gmi_credentials() or not settings.gmi_vision_model:
        return []

    api_key = settings.gmi_api_key.get_secret_value() if settings.gmi_api_key else ""
    endpoint = f"{settings.gmi_llm_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if settings.gmi_org_id:
        headers["X-Organization-ID"] = settings.gmi_org_id

    b64_img = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64_img}"

    prompt = (
        "Analyze this clothing photo for a digital wardrobe application. "
        "Identify all distinct garments worn or shown "
        "(tops, bottoms, outerwear, footwear, dresses, accessories). "
        "Return ONLY a JSON object with key 'garments' containing an array of objects. "
        "Each object must have:\n"
        "- name_suggestion: string (e.g. 'Navy Blue Wool Coat')\n"
        "- category: string ('top', 'bottom', 'outerwear', 'footwear', 'dress', 'accessory')\n"
        "- colors: array of strings\n"
        "- bbox: object with keys 'left', 'top', 'right', 'bottom' in pixel coordinates "
        "(0 to width, 0 to height)\n"
        "- apparent_material: string\n"
        "- pattern: string\n"
        "- confidence: number between 0.0 and 1.0\n"
        "- unresolved_details: array of strings\n"
        f"Image dimensions are width={width}, height={height}."
    )

    body = {
        "model": settings.gmi_vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 1000,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, headers=headers, json=body)
            if resp.status_code != 200:
                return []
            res_data = resp.json()
            content = res_data["choices"][0]["message"]["content"]
            # Extract JSON from markdown fences if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            items = parsed.get("garments", [])
            results: list[DetectedGarment] = []
            for item in items:
                bbox_raw = item.get("bbox", {})
                left = float(bbox_raw.get("left", 0))
                top = float(bbox_raw.get("top", 0))
                right = float(bbox_raw.get("right", width))
                bottom = float(bbox_raw.get("bottom", height))
                # Clamp coordinates to image boundaries
                left = max(0.0, min(left, float(width)))
                top = max(0.0, min(top, float(height)))
                right = max(left + 10.0, min(right, float(width)))
                bottom = max(top + 10.0, min(bottom, float(height)))

                results.append(
                    DetectedGarment(
                        name_suggestion=str(item.get("name_suggestion", "Extracted Garment")),
                        category=str(item.get("category", "top")).lower(),
                        colors=[str(c) for c in item.get("colors", ["unknown"])],
                        bbox={"left": left, "top": top, "right": right, "bottom": bottom},
                        apparent_material=str(item.get("apparent_material", "needs review")),
                        pattern=str(item.get("pattern", "needs review")),
                        confidence=float(item.get("confidence", 0.8)),
                        unresolved_details=[
                            str(u) for u in item.get("unresolved_details", [])
                        ],
                    )
                )
            return results
    except Exception:
        return []
