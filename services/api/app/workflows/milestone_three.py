from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ProviderMode, Settings, StorageMode
from app.core.errors import FitCheckError
from app.db.models import (
    Garment,
    GarmentAsset,
    GarmentEvidence,
    ModelProfile,
    OutfitItem,
    OutfitPlan,
    ProvenanceLink,
    TryOnRender,
    User,
    new_id,
)
from app.domain.enums import AssetEvidenceStatus, GarmentStatus, OutfitStatus
from app.domain.schemas import (
    ModelProfilePresignResponse,
    ModelProfileResponse,
    ModelProfileUploadRequest,
    TryOnRenderRequest,
    TryOnRenderResponse,
    TryOnSourceGarmentResponse,
)
from app.providers.contracts import GeneratedMedia, ImageGenerationRequest, MediaOrchestrator
from app.services.image_processing import inspect_upload_image
from app.services.object_keys import ObjectKeys
from app.services.provenance import MediaProvenanceManifest, persist_manifest
from app.services.storage import ObjectStorage, sha256_bytes
from app.services.task_queue import JobEvent, broadcaster

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_EXTENSIONS_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_AI_PREVIEW_DISCLOSURE = (
    "AI preview / visualization only. It may not reproduce true size, fit, fabric drape, "
    "body shape, or garment details exactly."
)


@dataclass(frozen=True, slots=True)
class _RenderSource:
    garment: Garment
    source_asset_id: str
    object_key: str
    image_url: str
    source_kind: str


class MilestoneThreeWorkflow:
    """Consent-gated selected-look previews with durable mock lineage.

    Mock mode produces a deliberately disclosed local AI-preview stand-in through
    the shared media-orchestrator contract. It never claims a source-verified
    virtual try-on. Live generation remains blocked until an explicitly
    configured, capability-tested GMI try-on model can return verifiable media.
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

    async def request_profile_upload(
        self,
        session: AsyncSession,
        payload: ModelProfileUploadRequest,
    ) -> ModelProfilePresignResponse:
        """Issue a private reference-photo target only after affirmative consent."""

        if not payload.consent:
            raise FitCheckError(
                "REFERENCE_PHOTO_CONSENT_REQUIRED",
                "Confirm consent before Fit Check stores a personal reference photo.",
                recommended_action=(
                    "Review the AI-preview disclosure, then confirm consent before uploading."
                ),
            )
        content_type = payload.content_type.lower()
        self._validate_profile_upload_request(content_type, payload.size_bytes)
        user = await self._ensure_demo_user(session)
        consented_at = datetime.now(UTC)
        profile_id = new_id()
        profile = ModelProfile(
            id=profile_id,
            user_id=user.id,
            source_image_key=self.keys.model_profile_reference(
                user.id,
                profile_id,
                _EXTENSIONS_BY_CONTENT_TYPE[content_type],
            ),
            sha256=f"pending-{profile_id}",
            status="pending_upload",
            consented_at=consented_at,
        )
        user.reference_photo_consent_at = consented_at
        session.add(profile)
        await session.commit()

        if self.settings.storage_mode is StorageMode.LOCAL:
            return ModelProfilePresignResponse(
                profile_id=profile.id,
                mode="api_proxy",
                upload_url=f"/v1/model-profiles/{profile.id}/content",
                source_image_key=profile.source_image_key,
            )

        signed_url = await self.storage.signed_upload_url(
            profile.source_image_key,
            content_type,
            self.settings.b2_presign_expires_seconds,
        )
        return ModelProfilePresignResponse(
            profile_id=profile.id,
            mode="direct_b2",
            upload_url=signed_url,
            source_image_key=profile.source_image_key,
            expires_in_seconds=self.settings.b2_presign_expires_seconds,
        )

    async def receive_local_profile_upload(
        self,
        session: AsyncSession,
        profile_id: str,
        content: bytes,
    ) -> ModelProfileResponse:
        if self.settings.storage_mode is not StorageMode.LOCAL:
            raise FitCheckError(
                "LOCAL_PROFILE_UPLOAD_ENDPOINT_DISABLED",
                "This reference photo uses a private direct-storage URL instead.",
            )
        return await self._finalize_profile(
            session,
            profile_id,
            content=content,
            persist_original=True,
        )

    async def finalize_profile(
        self, session: AsyncSession, profile_id: str
    ) -> ModelProfileResponse:
        """Validate a direct-to-B2 upload before exposing it to rendering."""

        user = await self._ensure_demo_user(session)
        profile = await self._owned_profile(session, user.id, profile_id, include_deleted=False)
        if profile.status == "active":
            return await self._profile_response(profile)
        if profile.status != "pending_upload":
            raise FitCheckError(
                "MODEL_PROFILE_NOT_READY",
                "This reference photo cannot be used until it is uploaded and validated.",
                entity_id=profile.id,
            )
        content = await self.storage.get_bytes(profile.source_image_key)
        return await self._finalize_profile(
            session,
            profile_id,
            content=content,
            persist_original=False,
        )

    async def list_profiles(self, session: AsyncSession) -> list[ModelProfileResponse]:
        user = await self._ensure_demo_user(session)
        profiles = list(
            (
                await session.scalars(
                    select(ModelProfile)
                    .where(
                        ModelProfile.user_id == user.id,
                        ModelProfile.deleted_at.is_(None),
                    )
                    .order_by(ModelProfile.created_at.desc())
                )
            ).all()
        )
        return [await self._profile_response(profile) for profile in profiles]

    async def delete_profile(self, session: AsyncSession, profile_id: str) -> None:
        """Remove a reference photo independently from wardrobe media and previews."""

        user = await self._ensure_demo_user(session)
        profile = await self._owned_profile(session, user.id, profile_id, include_deleted=True)
        if profile.deleted_at is not None:
            return
        await self.storage.delete(profile.source_image_key)
        profile.status = "deleted"
        profile.deleted_at = datetime.now(UTC)
        await session.commit()

    async def render_outfit(
        self,
        session: AsyncSession,
        outfit_id: str,
        payload: TryOnRenderRequest,
    ) -> TryOnRenderResponse:
        """Create one selected-look preview from a consented profile and owned garments."""

        user = await self._ensure_demo_user(session)
        outfit = await self._owned_outfit(session, user.id, outfit_id)
        if outfit.status == OutfitStatus.REJECTED.value:
            raise FitCheckError(
                "OUTFIT_NOT_RENDERABLE",
                "This rejected look cannot be used for an AI preview.",
                entity_id=outfit.id,
            )
        profile = await self._owned_profile(
            session, user.id, payload.profile_id, include_deleted=False
        )
        if profile.status != "active" or profile.deleted_at is not None:
            raise FitCheckError(
                "MODEL_PROFILE_NOT_READY",
                "Choose a saved, consented reference photo before rendering a preview.",
                entity_id=profile.id,
            )
        if profile.consented_at is None:
            raise FitCheckError(
                "REFERENCE_PHOTO_CONSENT_REQUIRED",
                "Fit Check needs consent before using a personal reference photo.",
                entity_id=profile.id,
            )

        sources = await self._render_sources(session, user.id, outfit, enforce_eligible=True)
        parent_run_id = await self._resolve_parent_run_id(
            session,
            user.id,
            outfit,
            profile,
            payload.parent_run_id,
        )
        previous_outfit_status = outfit.status
        render = TryOnRender(
            id=new_id(),
            outfit_id=outfit.id,
            profile_id=profile.id,
            parent_run_id=parent_run_id,
            status=OutfitStatus.PREVIEW_GENERATING.value,
            created_at=datetime.now(UTC),
        )
        session.add(render)
        outfit.status = OutfitStatus.PREVIEW_GENERATING.value
        await session.flush()

        requested_model: str | None = None
        generated: GeneratedMedia | None = None
        try:
            broadcaster.publish(
                JobEvent(
                    job_id=render.id,
                    stage="preview_generating",
                    progress=20,
                    data={"outfit_id": outfit.id, "profile_id": profile.id},
                )
            )
            requested_model = self._configured_tryon_model()
            if self.settings.provider_mode is not ProviderMode.MOCK:
                raise FitCheckError(
                    "TRYON_LIVE_INPUTS_UNVERIFIED",
                    (
                        "Live try-on stays disabled until the capability test confirms a "
                        "private, non-persistent reference-image input path."
                    ),
                    entity_id=render.id,
                    recommended_action=(
                        "Complete the configured GMI capability test before enabling live previews."
                    ),
                )
            generated = await self.orchestrator.generate_image(
                ImageGenerationRequest(
                    pipeline_slug="fit-check-m3-tryon-preview",
                    tenant_id=user.id,
                    garment_id=outfit.id,
                    prompt=self._tryon_prompt(payload.correction_hint),
                    prompt_redacted=(
                        "[consented selected-look AI preview; "
                        f"correction_hint_supplied={payload.correction_hint is not None}]"
                    ),
                    prompt_template_version="m3.tryon-preview/v1",
                    model=requested_model,
                    parent_run_id=parent_run_id,
                    source_asset_ids=(profile.id, *(source.source_asset_id for source in sources)),
                    source_urls=(
                        await self.storage.signed_read_url(profile.source_image_key),
                        *(source.image_url for source in sources),
                    ),
                    parameters={
                        "purpose": "selected_outfit_preview",
                        "output": "image/png",
                        "outfit_id": outfit.id,
                        "profile_id": profile.id,
                        "selected_garment_ids": [source.garment.id for source in sources],
                        "correction_hint_supplied": payload.correction_hint is not None,
                    },
                )
            )
            if generated.content is None:
                raise FitCheckError(
                    "GENERATION_OUTPUT_UNVERIFIABLE",
                    (
                        "The provider did not return a verifiable preview file, so Fit Check "
                        "did not mark it ready."
                    ),
                    retryable=True,
                    entity_id=render.id,
                    correlation_id=generated.run_id,
                    recommended_action=(
                        "Retry after the provider returns a verified image artifact."
                    ),
                )
            inspection = inspect_upload_image(generated.content)
            object_key = self.keys.look_render(user.id, render.id, 1)
            stored = await self.storage.put_bytes(
                object_key,
                generated.content,
                content_type=inspection.content_type,
                metadata={
                    "render-id": render.id,
                    "run-id": generated.run_id,
                    "profile-id": profile.id,
                    "outfit-id": outfit.id,
                    "disclosure": "ai-preview",
                },
            )
            persisted = await self.storage.head(object_key)
            if persisted.sha256 != stored.sha256:
                raise FitCheckError(
                    "STORAGE_HASH_MISMATCH",
                    "Saving the generated preview securely failed validation.",
                    retryable=True,
                    entity_id=render.id,
                    correlation_id=generated.run_id,
                )

            render.object_key = object_key
            render.sha256 = stored.sha256
            render.run_id = generated.run_id
            render.parent_run_id = parent_run_id
            render.status = OutfitStatus.PREVIEW_READY.value
            render.provider = generated.provider
            render.model = generated.model
            outfit.status = OutfitStatus.PREVIEW_READY.value

            manifest = self._success_manifest(
                render=render,
                outfit=outfit,
                profile=profile,
                sources=sources,
                generated=generated,
                requested_model=requested_model,
                correction_hint_supplied=payload.correction_hint is not None,
                inspection_width=inspection.width,
                inspection_height=inspection.height,
                content_type=inspection.content_type,
                output_size=stored.size,
            )
            manifest_key, manifest_hash = await persist_manifest(self.storage, self.keys, manifest)
            session.add(
                ProvenanceLink(
                    entity_type="tryon_render",
                    entity_id=render.id,
                    manifest_key=manifest_key,
                    manifest_hash=manifest_hash,
                    run_id=generated.run_id,
                    parent_run_id=parent_run_id,
                    privacy_scope="private",
                    redacted_manifest=manifest.owner_view(),
                )
            )
            await session.commit()
            broadcaster.publish(
                JobEvent(
                    job_id=render.id,
                    stage="preview_ready",
                    progress=100,
                    data={"render_id": render.id, "run_id": generated.run_id},
                )
            )
            return await self._render_response(session, render, profile=profile, sources=sources)
        except FitCheckError as error:
            await self._record_failed_render(
                session,
                render=render,
                outfit=outfit,
                previous_outfit_status=previous_outfit_status,
                profile=profile,
                sources=sources,
                error=error,
                generated=generated,
                requested_model=requested_model,
                correction_hint_supplied=payload.correction_hint is not None,
            )
            raise

    async def list_renders(
        self, session: AsyncSession, outfit_id: str
    ) -> list[TryOnRenderResponse]:
        user = await self._ensure_demo_user(session)
        outfit = await self._owned_outfit(session, user.id, outfit_id)
        renders = list(
            (
                await session.scalars(
                    select(TryOnRender)
                    .where(TryOnRender.outfit_id == outfit.id)
                    .order_by(TryOnRender.created_at.desc())
                )
            ).all()
        )
        return [await self._render_response(session, render) for render in renders]

    async def _finalize_profile(
        self,
        session: AsyncSession,
        profile_id: str,
        *,
        content: bytes,
        persist_original: bool,
    ) -> ModelProfileResponse:
        if not content:
            raise FitCheckError(
                "EMPTY_UPLOAD", "This reference photo is empty.", entity_id=profile_id
            )
        if len(content) > self.settings.max_upload_bytes:
            raise FitCheckError(
                "UPLOAD_TOO_LARGE",
                "This reference photo is larger than the private upload limit.",
                entity_id=profile_id,
            )
        user = await self._ensure_demo_user(session)
        profile = await self._owned_profile(session, user.id, profile_id, include_deleted=False)
        if profile.status == "active":
            return await self._profile_response(profile)
        if profile.status != "pending_upload":
            raise FitCheckError(
                "MODEL_PROFILE_NOT_READY",
                "This reference photo cannot be validated in its current state.",
                entity_id=profile.id,
            )
        inspection = inspect_upload_image(content)
        source_hash = sha256_bytes(content)
        if persist_original:
            stored = await self.storage.put_bytes(
                profile.source_image_key,
                content,
                content_type=inspection.content_type,
                metadata={
                    "profile-id": profile.id,
                    "source-sha256": source_hash,
                    "consented-at": profile.consented_at.isoformat(),
                },
            )
            if stored.sha256 != source_hash:
                raise FitCheckError(
                    "STORAGE_HASH_MISMATCH",
                    "Saving the reference photo securely failed validation.",
                    retryable=True,
                    entity_id=profile.id,
                )
        else:
            stored = await self.storage.head(profile.source_image_key)
            if stored.size != len(content):
                raise FitCheckError(
                    "STORAGE_VALIDATION_FAILED",
                    "Saving the reference photo securely failed validation.",
                    retryable=True,
                    entity_id=profile.id,
                )

        profile.sha256 = source_hash
        profile.status = "active"
        await session.commit()
        return await self._profile_response(profile)

    async def _record_failed_render(
        self,
        session: AsyncSession,
        *,
        render: TryOnRender,
        outfit: OutfitPlan,
        previous_outfit_status: str,
        profile: ModelProfile,
        sources: list[_RenderSource],
        error: FitCheckError,
        generated: GeneratedMedia | None,
        requested_model: str | None,
        correction_hint_supplied: bool,
    ) -> None:
        """Persist a retryable failure without losing the selected outfit or lineage."""

        failure_run_id = f"tryon-failed-{render.id}"
        render.run_id = failure_run_id
        render.status = "failed"
        render.provider = generated.provider if generated is not None else self._default_provider()
        render.model = generated.model if generated is not None else requested_model
        render.error_code = error.code
        render.error_message = error.message
        outfit.status = previous_outfit_status
        manifest = MediaProvenanceManifest(
            run_id=failure_run_id,
            parent_run_id=render.parent_run_id,
            pipeline_slug="fit-check-m3-tryon-preview",
            tenant_id=profile.user_id,
            status="failed",
            provider=render.provider or self._default_provider(),
            model=render.model or "unconfigured",
            prompt_template_version="m3.tryon-preview/v1",
            prompt_redacted=(
                "[consented selected-look AI preview; "
                f"correction_hint_supplied={correction_hint_supplied}]"
            ),
            generation_parameters={
                "purpose": "selected_outfit_preview",
                "outfit_id": outfit.id,
                "profile_id": profile.id,
                "selected_garment_ids": [source.garment.id for source in sources],
                "requested_model": requested_model,
                "correction_hint_supplied": correction_hint_supplied,
            },
            source_asset_ids=[profile.id, *(source.source_asset_id for source in sources)],
            source_object_keys=[
                profile.source_image_key,
                *(source.object_key for source in sources),
            ],
            output={"render_id": render.id, "object_key": None, "sha256": None},
            transformations=[self._selected_outfit_transformation(outfit, sources)],
            retry_history=list(generated.retry_history) if generated is not None else [],
            qa={
                "status": "not_generated",
                "evidence_status": AssetEvidenceStatus.AI_RECONSTRUCTED.value,
                "disclosure": _AI_PREVIEW_DISCLOSURE,
                "error_code": error.code,
                "provider_correlation_id": error.correlation_id,
                "retryable": error.retryable,
            },
        )
        manifest_key, manifest_hash = await persist_manifest(self.storage, self.keys, manifest)
        session.add(
            ProvenanceLink(
                entity_type="tryon_render",
                entity_id=render.id,
                manifest_key=manifest_key,
                manifest_hash=manifest_hash,
                run_id=failure_run_id,
                parent_run_id=render.parent_run_id,
                privacy_scope="private",
                redacted_manifest=manifest.owner_view(),
            )
        )
        await session.commit()

    def _success_manifest(
        self,
        *,
        render: TryOnRender,
        outfit: OutfitPlan,
        profile: ModelProfile,
        sources: list[_RenderSource],
        generated: GeneratedMedia,
        requested_model: str | None,
        correction_hint_supplied: bool,
        inspection_width: int,
        inspection_height: int,
        content_type: str,
        output_size: int,
    ) -> MediaProvenanceManifest:
        assert render.run_id is not None
        assert render.object_key is not None
        assert render.sha256 is not None
        return MediaProvenanceManifest(
            run_id=render.run_id,
            parent_run_id=render.parent_run_id,
            pipeline_slug="fit-check-m3-tryon-preview",
            tenant_id=profile.user_id,
            provider=generated.provider,
            model=generated.model,
            prompt_template_version="m3.tryon-preview/v1",
            prompt_redacted=(
                "[consented selected-look AI preview; "
                f"correction_hint_supplied={correction_hint_supplied}]"
            ),
            generation_parameters={
                "purpose": "selected_outfit_preview",
                "outfit_id": outfit.id,
                "profile_id": profile.id,
                "selected_garment_ids": [source.garment.id for source in sources],
                "requested_model": requested_model,
                "correction_hint_supplied": correction_hint_supplied,
            },
            source_asset_ids=[profile.id, *(source.source_asset_id for source in sources)],
            source_object_keys=[
                profile.source_image_key,
                *(source.object_key for source in sources),
            ],
            output={
                "render_id": render.id,
                "object_key": render.object_key,
                "sha256": render.sha256,
                "content_type": content_type,
                "bytes": output_size,
            },
            transformations=[
                self._selected_outfit_transformation(outfit, sources),
                {
                    "name": "output_decode_validation",
                    "width": inspection_width,
                    "height": inspection_height,
                    "content_type": content_type,
                    "passed": True,
                },
            ],
            retry_history=list(generated.retry_history),
            qa={
                "status": "decoded",
                "review_required": False,
                "evidence_status": AssetEvidenceStatus.AI_RECONSTRUCTED.value,
                "disclosure": _AI_PREVIEW_DISCLOSURE,
            },
        )

    async def _render_response(
        self,
        session: AsyncSession,
        render: TryOnRender,
        *,
        profile: ModelProfile | None = None,
        sources: list[_RenderSource] | None = None,
    ) -> TryOnRenderResponse:
        if profile is None:
            profile = await session.scalar(
                select(ModelProfile).where(ModelProfile.id == render.profile_id)
            )
        if profile is None:
            raise FitCheckError(
                "MODEL_PROFILE_NOT_FOUND",
                "The reference photo for this preview is unavailable.",
                entity_id=render.profile_id,
            )
        outfit = await session.scalar(select(OutfitPlan).where(OutfitPlan.id == render.outfit_id))
        if outfit is None:
            raise FitCheckError(
                "OUTFIT_NOT_FOUND", "That look is unavailable.", entity_id=render.outfit_id
            )
        resolved_sources = sources or await self._render_sources(
            session, profile.user_id, outfit, enforce_eligible=False
        )
        render_url = (
            await self.storage.signed_read_url(render.object_key) if render.object_key else None
        )
        reference_image_url = (
            await self.storage.signed_read_url(profile.source_image_key)
            if profile.status == "active" and profile.deleted_at is None
            else None
        )
        return TryOnRenderResponse(
            id=render.id,
            outfit_id=render.outfit_id,
            profile_id=render.profile_id,
            status=render.status,
            object_key=render.object_key,
            render_url=render_url,
            sha256=render.sha256,
            run_id=render.run_id,
            parent_run_id=render.parent_run_id,
            provider=render.provider,
            model=render.model,
            error_code=render.error_code,
            error_message=render.error_message,
            source_garment_ids=[source.garment.id for source in resolved_sources],
            source_garments=[
                TryOnSourceGarmentResponse(
                    id=source.garment.id,
                    name=source.garment.name,
                    category=source.garment.category,
                    colors=list(source.garment.colors),
                    evidence_status=source.garment.evidence_status,
                    source_kind=source.source_kind,
                    image_url=source.image_url,
                )
                for source in resolved_sources
            ],
            reference_image_url=reference_image_url,
            disclosure=_AI_PREVIEW_DISCLOSURE,
            created_at=render.created_at,
        )

    async def _render_sources(
        self,
        session: AsyncSession,
        user_id: str,
        outfit: OutfitPlan,
        *,
        enforce_eligible: bool,
    ) -> list[_RenderSource]:
        rows = list(
            (
                await session.execute(
                    select(OutfitItem, Garment)
                    .join(Garment, OutfitItem.garment_id == Garment.id)
                    .where(OutfitItem.outfit_id == outfit.id)
                    .order_by(OutfitItem.created_at.asc())
                )
            ).tuples()
        )
        if not rows:
            raise FitCheckError(
                "OUTFIT_NOT_RENDERABLE",
                "This look has no owned garments to preview.",
                entity_id=outfit.id,
            )
        sources: list[_RenderSource] = []
        for _, garment in rows:
            if enforce_eligible and (
                garment.user_id != user_id
                or garment.status != GarmentStatus.APPROVED.value
                or garment.archived_at is not None
                or garment.deleted_at is not None
            ):
                raise FitCheckError(
                    "OUTFIT_NOT_RENDERABLE",
                    "Every selected garment must still be an approved owned wardrobe item.",
                    entity_id=outfit.id,
                    recommended_action="Choose another recommendation after reviewing the closet.",
                )
            asset = await self._approved_canonical_asset(session, garment)
            if asset is not None:
                sources.append(
                    _RenderSource(
                        garment=garment,
                        source_asset_id=asset.id,
                        object_key=asset.object_key,
                        image_url=await self.storage.signed_read_url(asset.object_key),
                        source_kind="approved_cutout",
                    )
                )
                continue
            evidence = await self._primary_evidence(session, garment.id)
            if evidence is None:
                if enforce_eligible:
                    raise FitCheckError(
                        "OUTFIT_NOT_RENDERABLE",
                        "A selected garment is missing its immutable source evidence.",
                        entity_id=garment.id,
                    )
                continue
            sources.append(
                _RenderSource(
                    garment=garment,
                    source_asset_id=evidence.id,
                    object_key=evidence.crop_key,
                    image_url=await self.storage.signed_read_url(evidence.crop_key),
                    source_kind="source_crop_fallback",
                )
            )
        if enforce_eligible and len(sources) != len(rows):
            raise FitCheckError(
                "OUTFIT_NOT_RENDERABLE",
                "Every selected garment needs a source-backed reference before previewing.",
                entity_id=outfit.id,
            )
        return sources

    async def _approved_canonical_asset(
        self, session: AsyncSession, garment: Garment
    ) -> GarmentAsset | None:
        if not garment.canonical_asset_id:
            return None
        return cast(
            GarmentAsset | None,
            await session.scalar(
                select(GarmentAsset).where(
                    GarmentAsset.id == garment.canonical_asset_id,
                    GarmentAsset.kind == "cutout",
                    GarmentAsset.qa_status == "approved",
                    GarmentAsset.deleted_at.is_(None),
                )
            ),
        )

    async def _primary_evidence(
        self, session: AsyncSession, garment_id: str
    ) -> GarmentEvidence | None:
        return cast(
            GarmentEvidence | None,
            await session.scalar(
                select(GarmentEvidence)
                .where(GarmentEvidence.garment_id == garment_id)
                .order_by(GarmentEvidence.created_at.asc())
            ),
        )

    async def _resolve_parent_run_id(
        self,
        session: AsyncSession,
        user_id: str,
        outfit: OutfitPlan,
        profile: ModelProfile,
        supplied_parent_run_id: str | None,
    ) -> str | None:
        if supplied_parent_run_id is not None:
            parent = await session.scalar(
                select(TryOnRender)
                .join(OutfitPlan, TryOnRender.outfit_id == OutfitPlan.id)
                .where(
                    OutfitPlan.user_id == user_id,
                    TryOnRender.outfit_id == outfit.id,
                    TryOnRender.profile_id == profile.id,
                    TryOnRender.run_id == supplied_parent_run_id,
                )
            )
            if parent is None:
                raise FitCheckError(
                    "TRYON_PARENT_RUN_NOT_FOUND",
                    "Choose a preview from this look and reference photo to retry.",
                    entity_id=outfit.id,
                )
            return parent.run_id

        previous = await session.scalar(
            select(TryOnRender)
            .where(
                TryOnRender.outfit_id == outfit.id,
                TryOnRender.profile_id == profile.id,
                TryOnRender.run_id.is_not(None),
            )
            .order_by(TryOnRender.created_at.desc())
        )
        if previous is not None and previous.run_id is not None:
            return previous.run_id
        return outfit.planner_run_id

    async def _owned_profile(
        self,
        session: AsyncSession,
        user_id: str,
        profile_id: str,
        *,
        include_deleted: bool,
    ) -> ModelProfile:
        statement = select(ModelProfile).where(
            ModelProfile.id == profile_id,
            ModelProfile.user_id == user_id,
        )
        if not include_deleted:
            statement = statement.where(ModelProfile.deleted_at.is_(None))
        profile = await session.scalar(statement)
        if profile is None:
            raise FitCheckError(
                "MODEL_PROFILE_NOT_FOUND",
                "That reference photo is unavailable.",
                entity_id=profile_id,
            )
        return profile

    async def _owned_outfit(
        self, session: AsyncSession, user_id: str, outfit_id: str
    ) -> OutfitPlan:
        outfit = await session.scalar(
            select(OutfitPlan).where(OutfitPlan.id == outfit_id, OutfitPlan.user_id == user_id)
        )
        if outfit is None:
            raise FitCheckError(
                "OUTFIT_NOT_FOUND", "That look is unavailable.", entity_id=outfit_id
            )
        return outfit

    async def _profile_response(self, profile: ModelProfile) -> ModelProfileResponse:
        is_active = profile.status == "active" and profile.deleted_at is None
        return ModelProfileResponse(
            id=profile.id,
            status=profile.status,
            source_image_key=profile.source_image_key,
            source_image_url=(
                await self.storage.signed_read_url(profile.source_image_key) if is_active else None
            ),
            sha256=profile.sha256 if is_active else None,
            consented_at=profile.consented_at,
            created_at=profile.created_at,
        )

    def _validate_profile_upload_request(self, content_type: str, size_bytes: int | None) -> None:
        if content_type not in _ALLOWED_CONTENT_TYPES:
            raise FitCheckError(
                "UNSUPPORTED_UPLOAD_TYPE",
                "Use a JPG, PNG, or WebP reference photo.",
                recommended_action="Convert HEIC photos to JPG before uploading.",
            )
        if size_bytes is not None and size_bytes > self.settings.max_upload_bytes:
            raise FitCheckError(
                "UPLOAD_TOO_LARGE",
                "This reference photo is larger than the private upload limit.",
                recommended_action=(
                    "Choose a photo no larger than "
                    f"{self.settings.max_upload_bytes // 1_048_576} MB."
                ),
            )

    def _configured_tryon_model(self) -> str | None:
        if self.settings.provider_mode is ProviderMode.MOCK:
            return None
        if not self.settings.gmi_tryon_model:
            raise FitCheckError(
                "TRYON_MODEL_NOT_CONFIGURED",
                "A capability-tested GMI try-on model has not been configured.",
                recommended_action=(
                    "Run the server-side capability smoke test, then set GMI_TRYON_MODEL."
                ),
            )
        return self.settings.gmi_tryon_model

    def _default_provider(self) -> str:
        return "mock" if self.settings.provider_mode is ProviderMode.MOCK else "gmicloud"

    def _tryon_prompt(self, correction_hint: str | None) -> str:
        correction_instruction = (
            " Apply this user-requested correction while preserving source evidence: "
            f"{correction_hint.strip()}"
            if correction_hint
            else ""
        )
        return (
            "Create one AI visualization of the consented reference person wearing the selected "
            "owned garment references. Preserve only source-supported garment features. Do not "
            "claim precise size, fit, fabric drape, or body shape. Avoid inventing additional "
            "garments, accessories, background details, or sensitive traits."
            f"{correction_instruction}"
        )

    def _selected_outfit_transformation(
        self, outfit: OutfitPlan, sources: list[_RenderSource]
    ) -> dict[str, object]:
        return {
            "name": "selected_outfit_assembly",
            "outfit_id": outfit.id,
            "garments": [
                {
                    "garment_id": source.garment.id,
                    "source_asset_id": source.source_asset_id,
                    "source_kind": source.source_kind,
                }
                for source in sources
            ],
        }

    async def _ensure_demo_user(self, session: AsyncSession) -> User:
        user = await session.scalar(select(User).where(User.id == self.settings.demo_user_id))
        if user is not None:
            return user
        user = User(
            id=self.settings.demo_user_id,
            auth_subject="demo:milestone-three",
            display_name="Fit Check demo",
            default_location="New York, NY",
        )
        session.add(user)
        await session.flush()
        return user
