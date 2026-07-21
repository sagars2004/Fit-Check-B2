from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    pipeline_slug: str
    tenant_id: str
    garment_id: str
    prompt: str
    prompt_redacted: str
    prompt_template_version: str
    model: str | None = None
    parent_run_id: str | None = None
    source_asset_ids: tuple[str, ...] = ()
    source_urls: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GeneratedMedia:
    run_id: str
    provider: str
    model: str
    content: bytes | None
    content_type: str
    source_asset_url: str | None = None
    provider_manifest: dict[str, Any] = field(default_factory=dict)
    retry_history: tuple[dict[str, Any], ...] = ()


class MediaOrchestrator(Protocol):
    async def generate_image(self, request: ImageGenerationRequest) -> GeneratedMedia: ...
