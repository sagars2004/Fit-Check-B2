from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.errors import FitCheckError
from app.providers.contracts import GeneratedMedia, ImageGenerationRequest
from app.providers.gmi import GenblazeGMICloudOrchestrator


@pytest.mark.asyncio
async def test_live_adapter_records_bounded_retry_history(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, gmi_max_retries=2)
    orchestrator = GenblazeGMICloudOrchestrator(settings)
    call_count = 0

    def fake_generate(_: ImageGenerationRequest) -> GeneratedMedia:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise FitCheckError(
                "GENBLAZE_EXECUTION_FAILED",
                "temporary provider failure",
                retryable=True,
                correlation_id="run-attempt",
            )
        return GeneratedMedia(
            run_id="final-run",
            provider="gmicloud",
            model="configured-model",
            content=None,
            content_type="image/png",
        )

    async def no_wait(_: float) -> None:
        return None

    monkeypatch.setattr(orchestrator, "_generate_sync", fake_generate)
    monkeypatch.setattr("app.providers.gmi.asyncio.sleep", no_wait)

    generated = await orchestrator.generate_image(
        ImageGenerationRequest(
            pipeline_slug="fit-check-garment-cutout",
            tenant_id="tenant-1",
            garment_id="garment-1",
            prompt="test",
            prompt_redacted="test",
            prompt_template_version="v1",
        )
    )

    assert call_count == 3
    assert generated.run_id == "final-run"
    assert generated.retry_history == (
        {
            "attempt": 1,
            "error_code": "GENBLAZE_EXECUTION_FAILED",
            "correlation_id": "run-attempt",
            "backoff_seconds": 1.0,
        },
        {
            "attempt": 2,
            "error_code": "GENBLAZE_EXECUTION_FAILED",
            "correlation_id": "run-attempt",
            "backoff_seconds": 2.0,
        },
    )
