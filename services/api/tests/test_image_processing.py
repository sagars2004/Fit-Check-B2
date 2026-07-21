from app.providers.contracts import ImageGenerationRequest
from app.providers.mock import MockMediaOrchestrator
from app.services.image_processing import validate_cutout_png


async def test_mock_asset_passes_transparent_png_quality_gate() -> None:
    generated = await MockMediaOrchestrator().generate_image(
        ImageGenerationRequest(
            pipeline_slug="test",
            tenant_id="demo",
            garment_id="garment-1",
            prompt="mock garment",
            prompt_redacted="mock",
            prompt_template_version="test/v1",
        )
    )

    assert generated.content is not None
    qa = validate_cutout_png(generated.content)
    assert qa.passed
    assert qa.transparent_corner_count == 4
    assert qa.alpha_bbox is not None
