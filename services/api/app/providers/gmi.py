from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import FitCheckError
from app.providers.contracts import GeneratedMedia, ImageGenerationRequest


class GMICloudCapabilityClient:
    """Server-only GMI account probe. It never selects or writes a model ID."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        if not self.settings.has_gmi_credentials():
            raise FitCheckError(
                "GMI_CONFIGURATION_MISSING",
                "GMI credentials are not configured.",
                recommended_action="Set GMI_API_KEY only on the API/worker environment.",
            )
        headers = {
            "Authorization": f"Bearer {self.settings.gmi_api_key.get_secret_value()}",
            "Accept": "application/json",
        }
        if self.settings.gmi_org_id:
            headers["X-Organization-ID"] = self.settings.gmi_org_id
        return headers

    async def list_media_models(self) -> list[dict[str, Any]]:
        endpoint = f"{self.settings.gmi_request_queue_base_url.rstrip('/')}/apikey/models"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(endpoint, headers=self._headers())
            response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        for key in ("data", "models", "items"):
            value = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    async def describe_media_model(self, model_id: str) -> dict[str, Any]:
        endpoint = f"{self.settings.gmi_request_queue_base_url.rstrip('/')}/models/{model_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(endpoint, headers=self._headers())
            response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"raw": payload}

    async def list_llm_models(self) -> list[dict[str, Any]]:
        endpoint = f"{self.settings.gmi_llm_base_url.rstrip('/')}/models"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(endpoint, headers=self._headers())
            response.raise_for_status()
        payload = response.json()
        value = payload.get("data", []) if isinstance(payload, dict) else payload
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    async def smoke_test(self) -> dict[str, Any]:
        if not self.settings.enable_provider_smoke_tests:
            raise FitCheckError(
                "SMOKE_TEST_DISABLED",
                "Provider smoke tests are disabled.",
                recommended_action="Set ENABLE_PROVIDER_SMOKE_TESTS=true for a deliberate server-side probe.",
            )
        media_models, llm_models = await asyncio.gather(self.list_media_models(), self.list_llm_models())
        # IDs are returned to the server operator for explicit review; none is auto-selected.
        return {
            "media_models": media_models,
            "llm_models": llm_models,
            "selected_models": {
                "vision": self.settings.gmi_vision_model,
                "image": self.settings.gmi_image_model,
                "tryon": self.settings.gmi_tryon_model,
            },
        }


class GenblazeGMICloudOrchestrator:
    """Production adapter: GMI Cloud generation through Genblaze + B2 sink.

    It is intentionally not called until the model capability probe has chosen a
    configured model. Genblaze owns provider retry/polling and writes its own
    hash-verified run manifest to the configured B2 sink.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_image(self, request: ImageGenerationRequest) -> GeneratedMedia:
        return await asyncio.to_thread(self._generate_sync, request)

    def _generate_sync(self, request: ImageGenerationRequest) -> GeneratedMedia:
        if not self.settings.has_gmi_credentials():
            raise FitCheckError("GMI_CONFIGURATION_MISSING", "GMI credentials are not configured.")
        model = request.model or self.settings.selected_image_model()
        if not self.settings.b2_bucket:
            raise FitCheckError("B2_CONFIGURATION_MISSING", "Live generation requires private B2 storage.")

        # SDK imports stay isolated from mock mode and preserve the official
        # Genblaze pipeline + B2 ObjectStorageSink architecture.
        from genblaze_core import KeyStrategy, Modality, ObjectStorageSink, Pipeline
        from genblaze_gmicloud import GMICloudImageProvider
        from genblaze_s3 import S3StorageBackend

        os.environ.setdefault("B2_KEY_ID", self.settings.b2_key_id.get_secret_value() if self.settings.b2_key_id else "")
        os.environ.setdefault("B2_APP_KEY", self.settings.b2_app_key.get_secret_value() if self.settings.b2_app_key else "")
        sink = ObjectStorageSink(
            S3StorageBackend.for_backblaze(self.settings.b2_bucket),
            key_strategy=KeyStrategy.HIERARCHICAL,
        )
        provider = GMICloudImageProvider(api_key=self.settings.gmi_api_key.get_secret_value())
        step_kwargs: dict[str, Any] = {
            "model": model,
            "prompt": request.prompt,
            "modality": Modality.IMAGE,
            **request.parameters,
        }
        # The exact reference-input field is capability-dependent. The smoke
        # test records it before this live path is enabled.
        if request.source_urls:
            step_kwargs["reference_image_urls"] = list(request.source_urls)

        pipeline = Pipeline(request.pipeline_slug).step(provider, **step_kwargs)
        result = pipeline.run(sink=sink, timeout=self.settings.gmi_generation_timeout_seconds)
        run, manifest = _unpack_genblaze_result(result)
        step = run.steps[-1]
        if getattr(step, "status", None) != "succeeded" or not getattr(step, "assets", None):
            raise FitCheckError(
                "PROVIDER_GENERATION_FAILED",
                getattr(step, "error", "GMI did not return a generated image."),
                retryable=True,
                correlation_id=str(getattr(run, "id", "")) or None,
            )
        asset = step.assets[0]
        return GeneratedMedia(
            run_id=str(getattr(run, "id", None) or getattr(manifest, "run_id", "")),
            provider="gmicloud",
            model=model,
            content=None,
            content_type=getattr(asset, "content_type", "image/png"),
            source_asset_url=getattr(asset, "url", None),
            provider_manifest=_model_to_dict(manifest),
        )


def _unpack_genblaze_result(result: Any) -> tuple[Any, Any]:
    if isinstance(result, tuple) and len(result) == 2:
        return result
    run = getattr(result, "run", None)
    manifest = getattr(result, "manifest", None)
    if run is not None and manifest is not None:
        return run, manifest
    raise RuntimeError("Unexpected Genblaze run result shape.")


def _model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {"raw": dumped}
    if hasattr(value, "dict") and inspect.ismethod(value.dict):
        dumped = value.dict()
        return dumped if isinstance(dumped, dict) else {"raw": dumped}
    return {"raw": str(value)}

