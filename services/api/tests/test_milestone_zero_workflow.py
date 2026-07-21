import json

from sqlalchemy import select

from app.core.config import ProviderMode, Settings, StorageMode
from app.db.models import GarmentAsset, ProvenanceLink
from app.db.session import Database
from app.providers.factory import build_media_orchestrator
from app.services.provenance import MediaProvenanceManifest
from app.services.storage import build_storage
from app.workflows.milestone_zero import MilestoneZeroWorkflow


async def test_mock_workflow_persists_asset_and_provenance(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        provider_mode=ProviderMode.MOCK,
        storage_mode=StorageMode.LOCAL,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'fit-check.db'}",
        local_media_root=tmp_path / "media",
        public_media_base_url="http://testserver/v1/media",
        auto_create_schema=True,
    )
    database = Database(settings)
    await database.initialize()
    storage = build_storage(settings)
    workflow = MilestoneZeroWorkflow(settings, storage, build_media_orchestrator(settings))

    async with database.session() as session:
        result = await workflow.create_demo_cutout(session, garment_name="Test overshirt")

    stored = await storage.head(result.object_key)
    assert stored.sha256 == result.sha256
    assert stored.content_type == "image/png"

    manifest_data = json.loads((await storage.get_bytes(result.manifest_key)).decode("utf-8"))
    manifest = MediaProvenanceManifest.model_validate(manifest_data)
    assert manifest.canonical_hash() == result.manifest_hash
    assert manifest.output["asset_id"] == result.asset_id
    assert manifest.qa["evidence_status"] == "ai_reconstructed"

    async with database.session() as session:
        asset = await session.scalar(select(GarmentAsset).where(GarmentAsset.id == result.asset_id))
        link = await session.scalar(
            select(ProvenanceLink).where(ProvenanceLink.entity_id == result.asset_id)
        )
    assert asset is not None
    assert asset.object_key == result.object_key
    assert link is not None
    assert link.manifest_hash == result.manifest_hash

    await database.dispose()
