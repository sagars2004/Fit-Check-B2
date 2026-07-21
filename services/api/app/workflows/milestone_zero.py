from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ProviderMode, Settings
from app.core.errors import FitCheckError
from app.db.models import Garment, GarmentAsset, ProvenanceLink, User, new_id
from app.domain.enums import AssetEvidenceStatus, GarmentStatus
from app.domain.schemas import DemoAssetResponse
from app.providers.contracts import ImageGenerationRequest, MediaOrchestrator
from app.services.image_processing import validate_cutout_png
from app.services.object_keys import ObjectKeys
from app.services.provenance import MediaProvenanceManifest, persist_manifest
from app.services.storage import ObjectStorage


class MilestoneZeroWorkflow:
    """Offline proof of the durable asset + provenance path.

    This endpoint intentionally produces an AI-reconstructed *demo* cutout. It
    never presents the result as a verified garment extraction; source-backed
    imports and approval gates arrive in Milestone 1.
    """

    def __init__(
        self,
        settings: Settings,
        storage: ObjectStorage,
        orchestrator: MediaOrchestrator,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.orchestrator = orchestrator
        self.keys = ObjectKeys(settings.b2_prefix)

    async def create_demo_cutout(
        self,
        session: AsyncSession,
        *,
        garment_name: str,
        parent_run_id: str | None = None,
    ) -> DemoAssetResponse:
        if self.settings.provider_mode is not ProviderMode.MOCK:
            raise FitCheckError(
                "DEMO_ENDPOINT_DISABLED",
                "The mock demo endpoint is available only in mock provider mode.",
            )

        user = await self._ensure_demo_user(session)
        garment_id = new_id()
        asset_id = new_id()
        garment = Garment(
            id=garment_id,
            user_id=user.id,
            name=garment_name,
            category="top",
            colors=["navy"],
            tags=["milestone-0", "demo"],
            seasons=[],
            status=GarmentStatus.READY.value,
            evidence_status=AssetEvidenceStatus.AI_RECONSTRUCTED.value,
            notes=(
                "Offline mock asset for storage and provenance verification. "
                "It is not source-backed wardrobe evidence."
            ),
        )
        session.add(garment)

        generation = await self.orchestrator.generate_image(
            ImageGenerationRequest(
                pipeline_slug="fit-check-m0-cutout",
                tenant_id=user.id,
                garment_id=garment_id,
                prompt=(
                    "Create a neutral catalog garment cutout. This offline demo prompt "
                    "does not represent a real user's clothing."
                ),
                prompt_redacted="[offline mock cutout prompt]",
                prompt_template_version="m0.mock-cutout/v1",
                parent_run_id=parent_run_id,
                parameters={"output": "transparent_png", "purpose": "milestone_0_proof"},
            )
        )
        if generation.content is None:
            raise FitCheckError(
                "DEMO_MEDIA_MISSING",
                "The configured demo provider did not return a local image.",
                retryable=True,
            )

        qa = validate_cutout_png(generation.content)
        if not qa.passed:
            raise FitCheckError(
                "CUTOUT_QA_FAILED",
                "The demo cutout failed deterministic alpha validation.",
                retryable=False,
            )

        object_key = self.keys.garment_cutout(user.id, garment_id, 1)
        stored = await self.storage.put_bytes(
            object_key,
            generation.content,
            content_type=generation.content_type,
            metadata={
                "asset-id": asset_id,
                "run-id": generation.run_id,
                "evidence-status": AssetEvidenceStatus.AI_RECONSTRUCTED.value,
            },
        )
        persisted = await self.storage.head(object_key)
        if persisted.sha256 != stored.sha256:
            raise FitCheckError(
                "STORAGE_HASH_MISMATCH",
                "Saving securely failed validation.",
                retryable=True,
                correlation_id=generation.run_id,
            )

        created_at = datetime.now(UTC)
        manifest = MediaProvenanceManifest(
            run_id=generation.run_id,
            parent_run_id=parent_run_id,
            pipeline_slug="fit-check-m0-cutout",
            tenant_id=user.id,
            created_at=created_at,
            provider=generation.provider,
            model=generation.model,
            prompt_template_version="m0.mock-cutout/v1",
            prompt_redacted="[offline mock cutout prompt]",
            generation_parameters={"output": "transparent_png", "purpose": "milestone_0_proof"},
            output={
                "asset_id": asset_id,
                "object_key": object_key,
                "sha256": stored.sha256,
                "content_type": generation.content_type,
                "bytes": stored.size,
            },
            transformations=[
                {"name": "deterministic_mock_generation", "version": "m0"},
                {
                    "name": "alpha_qa",
                    "passed": qa.passed,
                    "warnings": list(qa.warnings),
                    "transparent_corners": qa.transparent_corner_count,
                    "alpha_bbox": list(qa.alpha_bbox) if qa.alpha_bbox else None,
                },
            ],
            retry_history=list(generation.retry_history),
            qa={
                "status": "passed",
                "warnings": list(qa.warnings),
                "review_required": True,
                "evidence_status": AssetEvidenceStatus.AI_RECONSTRUCTED.value,
            },
        )
        manifest_key, manifest_hash = await persist_manifest(self.storage, self.keys, manifest)

        asset = GarmentAsset(
            id=asset_id,
            garment_id=garment_id,
            kind="cutout",
            object_key=object_key,
            sha256=stored.sha256,
            version=1,
            qa_status="passed",
            qa_warnings=list(qa.warnings),
            evidence_status=AssetEvidenceStatus.AI_RECONSTRUCTED.value,
            run_id=generation.run_id,
            parent_run_id=parent_run_id,
            provider=generation.provider,
            model=generation.model,
            approved_at=None,
        )
        provenance_link = ProvenanceLink(
            entity_type="garment_asset",
            entity_id=asset_id,
            manifest_key=manifest_key,
            manifest_hash=manifest_hash,
            run_id=generation.run_id,
            parent_run_id=parent_run_id,
            privacy_scope="private",
            redacted_manifest=manifest.owner_view(),
        )
        garment.canonical_asset_id = asset_id
        session.add_all([asset, provenance_link])
        await session.commit()

        return DemoAssetResponse(
            asset_id=asset_id,
            garment_id=garment_id,
            run_id=generation.run_id,
            parent_run_id=parent_run_id,
            object_key=object_key,
            sha256=stored.sha256,
            manifest_key=manifest_key,
            manifest_hash=manifest_hash,
            evidence_status=AssetEvidenceStatus.AI_RECONSTRUCTED.value,
            provider=generation.provider,
            model=generation.model,
            created_at=created_at,
        )

    async def _ensure_demo_user(self, session: AsyncSession) -> User:
        user = await session.scalar(select(User).where(User.id == self.settings.demo_user_id))
        if user is not None:
            return user
        user = User(
            id=self.settings.demo_user_id,
            auth_subject="demo:milestone-zero",
            display_name="Fit Check demo",
            default_location="New York, NY",
        )
        session.add(user)
        await session.flush()
        return user
