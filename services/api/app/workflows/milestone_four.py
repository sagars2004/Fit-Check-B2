from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ProviderMode, Settings, StorageMode
from app.core.errors import FitCheckError
from app.db.models import Garment, GarmentAsset, GarmentEvidence, ProvenanceLink, User
from app.domain.enums import AssetEvidenceStatus, GarmentStatus
from app.domain.schemas import DemoSeedGarmentResponse, DemoSeedResponse
from app.services.image_processing import chroma_to_transparent, validate_cutout_png
from app.services.object_keys import ObjectKeys
from app.services.provenance import MediaProvenanceManifest, persist_manifest
from app.services.storage import LocalObjectStorage, ObjectStorage, StoredObject, sha256_bytes

_FIXTURE_VERSION = "m4.local-demo/v1"
_FIXTURE_CREATED_AT = datetime(2026, 7, 21, tzinfo=UTC)
_CUTOUT_MODEL = "deterministic-chroma-key/v1"
_SEED_DISCLOSURE = (
    "Synthetic local demo wardrobe only. Each approved item is traceable to its immutable "
    "synthetic source crop and deterministic cutout; it is not a personal upload or a real "
    "user-owned garment."
)
_REFERENCE_PHOTO_REQUIREMENT = (
    "No reference photo is seeded. To generate a selected-look AI preview, upload a reference "
    "photo only after explicitly confirming consent."
)


@dataclass(frozen=True, slots=True)
class _DemoGarmentSpec:
    garment_id: str
    evidence_id: str
    asset_id: str | None
    name: str
    category: str
    colors: tuple[str, ...]
    tags: tuple[str, ...]
    seasons: tuple[str, ...]
    price: Decimal
    status: str
    evidence_status: str
    silhouette: str
    fill: tuple[int, int, int]
    accent: tuple[int, int, int]

    @property
    def has_approved_cutout(self) -> bool:
        return self.asset_id is not None


# Fixed IDs make repeated seed requests idempotent. They are reserved for local
# fixture data and are never inferred from or applied to user-uploaded records.
_DEMO_GARMENTS: tuple[_DemoGarmentSpec, ...] = (
    _DemoGarmentSpec(
        garment_id="00000000-0000-0000-0000-000000000101",
        evidence_id="00000000-0000-0000-0000-000000000201",
        asset_id="00000000-0000-0000-0000-000000000301",
        name="Demo navy overshirt",
        category="top",
        colors=("navy",),
        tags=("work", "smart", "layer"),
        seasons=("spring", "fall"),
        price=Decimal("120.00"),
        status=GarmentStatus.APPROVED.value,
        evidence_status=AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value,
        silhouette="top",
        fill=(36, 57, 97),
        accent=(109, 137, 184),
    ),
    _DemoGarmentSpec(
        garment_id="00000000-0000-0000-0000-000000000102",
        evidence_id="00000000-0000-0000-0000-000000000202",
        asset_id="00000000-0000-0000-0000-000000000302",
        name="Demo charcoal trousers",
        category="trousers",
        colors=("gray",),
        tags=("work", "smart"),
        seasons=("spring", "fall", "winter"),
        price=Decimal("110.00"),
        status=GarmentStatus.APPROVED.value,
        evidence_status=AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value,
        silhouette="trousers",
        fill=(65, 72, 83),
        accent=(138, 145, 154),
    ),
    _DemoGarmentSpec(
        garment_id="00000000-0000-0000-0000-000000000103",
        evidence_id="00000000-0000-0000-0000-000000000203",
        asset_id="00000000-0000-0000-0000-000000000303",
        name="Demo cream knit",
        category="sweater",
        colors=("cream",),
        tags=("warm", "work", "comfortable"),
        seasons=("fall", "winter"),
        price=Decimal("90.00"),
        status=GarmentStatus.APPROVED.value,
        evidence_status=AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value,
        silhouette="sweater",
        fill=(227, 217, 190),
        accent=(170, 151, 113),
    ),
    _DemoGarmentSpec(
        garment_id="00000000-0000-0000-0000-000000000104",
        evidence_id="00000000-0000-0000-0000-000000000204",
        asset_id="00000000-0000-0000-0000-000000000304",
        name="Demo blue jeans",
        category="jeans",
        colors=("blue",),
        tags=("casual", "weekend"),
        seasons=("spring", "fall"),
        price=Decimal("80.00"),
        status=GarmentStatus.APPROVED.value,
        evidence_status=AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value,
        silhouette="jeans",
        fill=(55, 105, 170),
        accent=(144, 183, 221),
    ),
    _DemoGarmentSpec(
        garment_id="00000000-0000-0000-0000-000000000105",
        evidence_id="00000000-0000-0000-0000-000000000205",
        asset_id="00000000-0000-0000-0000-000000000305",
        name="Demo navy rain jacket",
        category="raincoat",
        colors=("navy",),
        tags=("rain", "warm", "commute"),
        seasons=("spring", "fall", "winter"),
        price=Decimal("150.00"),
        status=GarmentStatus.APPROVED.value,
        evidence_status=AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value,
        silhouette="raincoat",
        fill=(31, 50, 89),
        accent=(71, 163, 188),
    ),
    _DemoGarmentSpec(
        garment_id="00000000-0000-0000-0000-000000000106",
        evidence_id="00000000-0000-0000-0000-000000000206",
        asset_id="00000000-0000-0000-0000-000000000306",
        name="Demo black boots",
        category="boots",
        colors=("black",),
        tags=("rain", "winter", "work"),
        seasons=("fall", "winter"),
        price=Decimal("140.00"),
        status=GarmentStatus.APPROVED.value,
        evidence_status=AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value,
        silhouette="boots",
        fill=(35, 37, 42),
        accent=(118, 122, 132),
    ),
    _DemoGarmentSpec(
        garment_id="00000000-0000-0000-0000-000000000107",
        evidence_id="00000000-0000-0000-0000-000000000207",
        asset_id=None,
        name="Demo patterned scarf — better photo needed",
        category="accessory",
        colors=("red", "navy"),
        tags=("review",),
        seasons=("fall", "winter"),
        price=Decimal("35.00"),
        status=GarmentStatus.NEEDS_BETTER_PHOTO.value,
        evidence_status=AssetEvidenceStatus.NEEDS_BETTER_PHOTO.value,
        silhouette="held",
        fill=(160, 71, 71),
        accent=(39, 56, 96),
    ),
)


class MilestoneFourDemoWorkflow:
    """Build an additive local fixture wardrobe without touching user media.

    This path is intentionally narrower than normal onboarding. It uses only
    in-process drawing and deterministic chroma removal, creates no provider
    run, and rejects both B2 and live-provider settings before accessing
    storage. Fixed fixture IDs let a judge retry safely while leaving all
    non-fixture records, previews, and user decisions untouched.
    """

    def __init__(self, settings: Settings, storage: ObjectStorage) -> None:
        self.settings = settings
        self.storage = storage
        self.keys = ObjectKeys(settings.b2_prefix)

    async def seed(self, session: AsyncSession) -> DemoSeedResponse:
        self._assert_local_mock_mode()
        user, created = await self._ensure_demo_user(session)
        fixture_garments: list[Garment] = []

        for spec in _DEMO_GARMENTS:
            garment, garment_created = await self._ensure_garment(session, user, spec)
            created = created or garment_created
            fixture_garments.append(garment)

            source_key = self.keys.garment_source_crop(user.id, spec.garment_id, spec.evidence_id)
            source_bytes = _source_crop_bytes(spec)
            source_stored, source_created = await self._ensure_object(
                source_key,
                source_bytes,
                content_type="image/jpeg",
                metadata={
                    "fixture-version": _FIXTURE_VERSION,
                    "fixture-kind": "synthetic-demo-source-crop",
                    "garment-id": spec.garment_id,
                    "evidence-status": spec.evidence_status,
                },
            )
            created = created or source_created
            evidence_created = await self._ensure_evidence(
                session,
                garment,
                spec,
                source_key=source_key,
                source_sha256=source_stored.sha256,
            )
            created = created or evidence_created

            if spec.asset_id is None:
                continue

            cutout_bytes, qa_warnings = _source_backed_cutout_bytes(source_bytes)
            cutout_key = self.keys.garment_cutout(user.id, spec.garment_id, 1)
            cutout_stored, cutout_created = await self._ensure_object(
                cutout_key,
                cutout_bytes,
                content_type="image/png",
                metadata={
                    "fixture-version": _FIXTURE_VERSION,
                    "fixture-kind": "synthetic-demo-source-cutout",
                    "asset-id": spec.asset_id,
                    "source-evidence-id": spec.evidence_id,
                    "qa-status": "approved",
                },
            )
            created = created or cutout_created
            manifest = self._cutout_manifest(
                user_id=user.id,
                spec=spec,
                source_key=source_key,
                source_sha256=source_stored.sha256,
                cutout_key=cutout_key,
                cutout_stored=cutout_stored,
                qa_warnings=qa_warnings,
            )
            manifest_key, manifest_hash, manifest_created = await self._ensure_manifest(manifest)
            created = created or manifest_created
            asset_created = await self._ensure_asset_and_provenance(
                session,
                garment,
                spec,
                cutout_key=cutout_key,
                cutout_sha256=cutout_stored.sha256,
                qa_warnings=qa_warnings,
                manifest_key=manifest_key,
                manifest_hash=manifest_hash,
                run_id=manifest.run_id,
                redacted_manifest=manifest.owner_view(),
            )
            created = created or asset_created

        await session.commit()
        approved_ids = [
            garment.id
            for garment in fixture_garments
            if garment.status == GarmentStatus.APPROVED.value
            and garment.archived_at is None
            and garment.deleted_at is None
        ]
        held = next(spec for spec in _DEMO_GARMENTS if spec.asset_id is None)
        return DemoSeedResponse(
            mode="local_mock",
            fixture_version=_FIXTURE_VERSION,
            created=created,
            disclosure=_SEED_DISCLOSURE,
            garments=[
                DemoSeedGarmentResponse(
                    id=garment.id,
                    name=garment.name,
                    category=garment.category,
                    status=garment.status,
                    evidence_status=garment.evidence_status,
                )
                for garment in fixture_garments
            ],
            fixture_garment_ids=[spec.garment_id for spec in _DEMO_GARMENTS],
            approved_garment_ids=approved_ids,
            needs_better_photo_garment_id=held.garment_id,
            approved_garment_count=len(approved_ids),
            fixture_garment_count=len(fixture_garments),
            profile_seeded=False,
            reference_photo_requirement=_REFERENCE_PHOTO_REQUIREMENT,
        )

    def _assert_local_mock_mode(self) -> None:
        if (
            self.settings.provider_mode is not ProviderMode.MOCK
            or self.settings.storage_mode is not StorageMode.LOCAL
            or not isinstance(self.storage, LocalObjectStorage)
        ):
            raise FitCheckError(
                "DEMO_ENDPOINT_DISABLED",
                (
                    "The synthetic demo seed is available only with local mock storage "
                    "and provider mode."
                ),
                recommended_action=(
                    "Use PROVIDER_MODE=mock and STORAGE_MODE=local for the offline judge demo."
                ),
            )

    async def _ensure_demo_user(self, session: AsyncSession) -> tuple[User, bool]:
        user = await session.scalar(select(User).where(User.id == self.settings.demo_user_id))
        if user is not None:
            return user, False
        user = User(
            id=self.settings.demo_user_id,
            auth_subject="demo:local-owner",
            display_name="Fit Check local owner",
            default_location="New York, NY",
        )
        session.add(user)
        await session.flush()
        return user, True

    async def _ensure_garment(
        self,
        session: AsyncSession,
        user: User,
        spec: _DemoGarmentSpec,
    ) -> tuple[Garment, bool]:
        garment = await session.scalar(select(Garment).where(Garment.id == spec.garment_id))
        if garment is not None:
            if garment.user_id != user.id:
                raise _seed_conflict(spec.garment_id, "fixture garment ID belongs to another owner")
            return garment, False

        garment = Garment(
            id=spec.garment_id,
            user_id=user.id,
            name=spec.name,
            category=spec.category,
            colors=list(spec.colors),
            tags=[*spec.tags, "synthetic-demo-fixture"],
            seasons=list(spec.seasons),
            price=spec.price,
            notes=(
                "Synthetic local demo fixture. Its evidence and cutout are traceable to a "
                "locally generated source image; it is not a personal upload."
                if spec.has_approved_cutout
                else "Synthetic local demo fixture intentionally held for a clearer source photo."
            ),
            status=spec.status,
            evidence_status=spec.evidence_status,
            canonical_asset_id=spec.asset_id,
            created_at=_FIXTURE_CREATED_AT,
        )
        session.add(garment)
        await session.flush()
        return garment, True

    async def _ensure_evidence(
        self,
        session: AsyncSession,
        garment: Garment,
        spec: _DemoGarmentSpec,
        *,
        source_key: str,
        source_sha256: str,
    ) -> bool:
        evidence = await session.scalar(
            select(GarmentEvidence).where(GarmentEvidence.id == spec.evidence_id)
        )
        if evidence is not None:
            if (
                evidence.garment_id != garment.id
                or evidence.crop_key != source_key
                or evidence.sha256 != source_sha256
            ):
                raise _seed_conflict(
                    spec.evidence_id, "fixture source evidence differs from the seed"
                )
            return False
        session.add(
            GarmentEvidence(
                id=spec.evidence_id,
                garment_id=garment.id,
                crop_key=source_key,
                role="primary",
                notes=(
                    "Immutable synthetic local demo source crop. It exists only to make the "
                    "offline review and provenance path demonstrable."
                ),
                sha256=source_sha256,
                created_at=_FIXTURE_CREATED_AT,
            )
        )
        await session.flush()
        return True

    async def _ensure_asset_and_provenance(
        self,
        session: AsyncSession,
        garment: Garment,
        spec: _DemoGarmentSpec,
        *,
        cutout_key: str,
        cutout_sha256: str,
        qa_warnings: tuple[str, ...],
        manifest_key: str,
        manifest_hash: str,
        run_id: str,
        redacted_manifest: dict[str, Any],
    ) -> bool:
        assert spec.asset_id is not None
        created = False
        asset = await session.scalar(select(GarmentAsset).where(GarmentAsset.id == spec.asset_id))
        if asset is not None:
            if (
                asset.garment_id != garment.id
                or asset.object_key != cutout_key
                or asset.sha256 != cutout_sha256
                or asset.kind != "cutout"
                or asset.qa_status != "approved"
                or asset.evidence_status != AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value
            ):
                raise _seed_conflict(spec.asset_id, "fixture cutout differs from the seed")
        else:
            session.add(
                GarmentAsset(
                    id=spec.asset_id,
                    garment_id=garment.id,
                    kind="cutout",
                    object_key=cutout_key,
                    sha256=cutout_sha256,
                    version=1,
                    qa_status="approved",
                    qa_warnings=list(qa_warnings),
                    evidence_status=AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value,
                    run_id=run_id,
                    parent_run_id=None,
                    provider="local",
                    model=_CUTOUT_MODEL,
                    approved_at=_FIXTURE_CREATED_AT,
                    created_at=_FIXTURE_CREATED_AT,
                )
            )
            created = True

        link = await session.scalar(
            select(ProvenanceLink).where(
                ProvenanceLink.entity_type == "garment_asset",
                ProvenanceLink.entity_id == spec.asset_id,
            )
        )
        if link is not None:
            if (
                link.deleted_at is not None
                or link.manifest_key != manifest_key
                or link.manifest_hash != manifest_hash
                or link.run_id != run_id
                or link.parent_run_id is not None
            ):
                raise _seed_conflict(spec.asset_id, "fixture provenance differs from the seed")
        else:
            existing_run = await session.scalar(
                select(ProvenanceLink).where(ProvenanceLink.run_id == run_id)
            )
            if existing_run is not None:
                raise _seed_conflict(spec.asset_id, "fixture provenance run ID is already in use")
            session.add(
                ProvenanceLink(
                    entity_type="garment_asset",
                    entity_id=spec.asset_id,
                    manifest_key=manifest_key,
                    manifest_hash=manifest_hash,
                    run_id=run_id,
                    parent_run_id=None,
                    privacy_scope="private",
                    redacted_manifest=redacted_manifest,
                )
            )
            created = True
        await session.flush()
        return created

    async def _ensure_object(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        metadata: dict[str, str],
    ) -> tuple[StoredObject, bool]:
        expected_hash = sha256_bytes(content)
        try:
            existing = await self.storage.head(key)
        except FitCheckError as error:
            if error.code != "OBJECT_NOT_FOUND":
                raise
            stored = await self.storage.put_bytes(
                key,
                content,
                content_type=content_type,
                metadata=metadata,
            )
            persisted = await self.storage.head(key)
            if (
                stored.sha256 != expected_hash
                or persisted.sha256 != expected_hash
                or persisted.size != len(content)
            ):
                raise FitCheckError(
                    "STORAGE_HASH_MISMATCH",
                    "Saving a local demo fixture failed validation.",
                    retryable=True,
                    entity_id=key,
                ) from error
            return persisted, True
        if (
            existing.sha256 != expected_hash
            or existing.size != len(content)
            or existing.content_type != content_type
        ):
            raise _seed_conflict(key, "fixture object already exists with different content")
        return existing, False

    async def _ensure_manifest(self, manifest: MediaProvenanceManifest) -> tuple[str, str, bool]:
        expected_hash = manifest.canonical_hash()
        manifest_key = self.keys.manifest(manifest.tenant_id, manifest.run_id)
        try:
            existing_content = await self.storage.get_bytes(manifest_key)
        except FitCheckError as error:
            if error.code != "OBJECT_NOT_FOUND":
                raise
            persisted_key, persisted_hash = await persist_manifest(
                self.storage, self.keys, manifest
            )
            if persisted_key != manifest_key or persisted_hash != expected_hash:
                raise FitCheckError(
                    "STORAGE_HASH_MISMATCH",
                    "Saving a local demo provenance record failed validation.",
                    retryable=True,
                    entity_id=manifest.run_id,
                ) from error
            return persisted_key, persisted_hash, True
        try:
            existing = MediaProvenanceManifest.model_validate_json(existing_content)
        except ValueError as error:
            raise _seed_conflict(
                manifest.run_id, "fixture provenance manifest is invalid"
            ) from error
        if existing.manifest_hash != expected_hash or existing.canonical_hash() != expected_hash:
            raise _seed_conflict(
                manifest.run_id, "fixture provenance manifest differs from the seed"
            )
        return manifest_key, expected_hash, False

    def _cutout_manifest(
        self,
        *,
        user_id: str,
        spec: _DemoGarmentSpec,
        source_key: str,
        source_sha256: str,
        cutout_key: str,
        cutout_stored: StoredObject,
        qa_warnings: tuple[str, ...],
    ) -> MediaProvenanceManifest:
        assert spec.asset_id is not None
        return MediaProvenanceManifest(
            run_id=_fixture_run_id(spec.asset_id),
            parent_run_id=None,
            pipeline_slug="fit-check-m4-demo-source-cutout",
            tenant_id=user_id,
            created_at=_FIXTURE_CREATED_AT,
            provider="local",
            model=_CUTOUT_MODEL,
            prompt_template_version="m4.synthetic-demo-source/v1",
            prompt_redacted="[no generative prompt; deterministic synthetic demo fixture]",
            generation_parameters={
                "fixture_version": _FIXTURE_VERSION,
                "source_is_personal_upload": False,
                "source_kind": "synthetic_local_fixture",
                "output": "transparent_png",
            },
            source_asset_ids=[spec.evidence_id],
            source_object_keys=[source_key],
            output={
                "asset_id": spec.asset_id,
                "object_key": cutout_key,
                "sha256": cutout_stored.sha256,
                "content_type": cutout_stored.content_type,
                "bytes": cutout_stored.size,
            },
            transformations=[
                {
                    "name": "synthetic_demo_source_fixture",
                    "fixture_version": _FIXTURE_VERSION,
                    "source_sha256": source_sha256,
                },
                {"name": "deterministic_chroma_removal", "green_bias": 32},
                {
                    "name": "transparent_alpha_qa",
                    "passed": True,
                    "warnings": list(qa_warnings),
                },
            ],
            qa={
                "status": "approved_demo_fixture",
                "warnings": list(qa_warnings),
                "review_required": False,
                "evidence_status": AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value,
                "synthetic_demo_fixture": True,
                "disclosure": _SEED_DISCLOSURE,
            },
        )


def _fixture_run_id(asset_id: str) -> str:
    return f"demo-m4-cutout-{asset_id}"


def _seed_conflict(entity_id: str, detail: str) -> FitCheckError:
    return FitCheckError(
        "DEMO_SEED_CONFLICT",
        "The local demo seed found existing fixture data it will not overwrite.",
        entity_id=entity_id,
        recommended_action=(
            "Keep existing data as-is, or use a new local database/media directory "
            "for a fresh demo. "
            f"Conflict: {detail}."
        ),
    )


def _source_backed_cutout_bytes(source: bytes) -> tuple[bytes, tuple[str, ...]]:
    cutout = chroma_to_transparent(source)
    qa = validate_cutout_png(cutout)
    if not qa.passed:
        raise FitCheckError(
            "DEMO_SEED_INVALID_FIXTURE",
            "A deterministic local demo cutout failed alpha quality checks.",
            retryable=False,
            recommended_action=(
                "Use the checked-in fixture generator rather than editing demo media."
            ),
        )
    return cutout, qa.warnings


def _source_crop_bytes(spec: _DemoGarmentSpec) -> bytes:
    """Create a stable, non-personal green-screen fixture source image locally."""

    image = Image.new("RGB", (512, 640), (20, 188, 38))
    draw = ImageDraw.Draw(image)
    fill = spec.fill
    accent = spec.accent
    outline = tuple(max(0, value - 35) for value in fill)

    if spec.silhouette in {"top", "sweater", "raincoat"}:
        top = 122 if spec.silhouette != "raincoat" else 102
        bottom = 502 if spec.silhouette != "raincoat" else 548
        draw.rounded_rectangle(
            (157, top, 355, bottom), radius=25, fill=fill, outline=outline, width=6
        )
        draw.polygon(
            ((157, top + 30), (89, top + 112), (122, top + 211), (179, top + 161)), fill=fill
        )
        draw.polygon(
            ((355, top + 30), (423, top + 112), (390, top + 211), (333, top + 161)), fill=fill
        )
        draw.polygon(((212, top), (256, top + 48), (300, top)), fill=accent)
        if spec.silhouette == "sweater":
            for y in range(top + 132, bottom - 24, 42):
                draw.line((181, y, 331, y), fill=accent, width=4)
        if spec.silhouette == "raincoat":
            draw.line((256, top + 64, 256, bottom - 18), fill=accent, width=6)
            for y in (top + 182, top + 264):
                draw.line((177, y, 335, y), fill=accent, width=4)
    elif spec.silhouette in {"trousers", "jeans"}:
        draw.rounded_rectangle((168, 102, 344, 246), radius=16, fill=fill, outline=outline, width=6)
        draw.polygon(((176, 236), (251, 236), (238, 548), (150, 548)), fill=fill)
        draw.polygon(((261, 236), (336, 236), (362, 548), (274, 548)), fill=fill)
        draw.line((256, 246, 256, 540), fill=accent, width=4)
        draw.line((177, 154, 335, 154), fill=accent, width=4)
    elif spec.silhouette == "boots":
        draw.rounded_rectangle((125, 204, 225, 476), radius=18, fill=fill, outline=outline, width=6)
        draw.rounded_rectangle((287, 204, 387, 476), radius=18, fill=fill, outline=outline, width=6)
        draw.rounded_rectangle((96, 446, 250, 520), radius=22, fill=fill, outline=outline, width=6)
        draw.rounded_rectangle((262, 446, 416, 520), radius=22, fill=fill, outline=outline, width=6)
        for y in (286, 336, 386):
            draw.line((143, y, 207, y), fill=accent, width=4)
            draw.line((305, y, 369, y), fill=accent, width=4)
    else:
        draw.rounded_rectangle((118, 196, 394, 438), radius=24, fill=fill, outline=outline, width=6)
        for x in range(150, 372, 42):
            draw.line((x, 220, x, 412), fill=accent, width=12)
        draw.line((132, 456, 380, 456), fill=outline, width=7)

    output = BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()
