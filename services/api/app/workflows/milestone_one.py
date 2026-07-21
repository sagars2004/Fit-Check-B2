from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, StorageMode
from app.core.errors import FitCheckError
from app.db.models import (
    Garment,
    GarmentCandidate,
    GarmentEvidence,
    ImportJob,
    Upload,
    User,
    new_id,
)
from app.domain.enums import AssetEvidenceStatus, GarmentStatus, ImportStatus
from app.domain.schemas import (
    CandidateResponse,
    CandidateReviewRequest,
    GarmentResponse,
    GarmentUpdateRequest,
    ImportJobResponse,
    UploadFinalizeResponse,
    UploadPresignRequest,
    UploadPresignResponse,
)
from app.services.image_processing import (
    approximate_color_name,
    crop_normalized_image,
    inspect_upload_image,
    normalize_image,
    perceptual_input_fingerprint,
)
from app.services.object_keys import ObjectKeys
from app.services.storage import ObjectStorage, sha256_bytes

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_EXTENSIONS_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class MilestoneOneWorkflow:
    """Private, deterministic import and review workflow for the local MVP.

    The workflow deliberately produces *source crops*, not invented cutouts.
    A crop remains evidence for a human to inspect; transparent cutout generation
    stays gated behind an approved item and a configured, capability-tested
    provider path.
    """

    def __init__(self, settings: Settings, storage: ObjectStorage) -> None:
        self.settings = settings
        self.storage = storage
        self.keys = ObjectKeys(settings.b2_prefix)

    async def request_upload(
        self, session: AsyncSession, payload: UploadPresignRequest
    ) -> UploadPresignResponse:
        if payload.content_type.lower() not in _ALLOWED_CONTENT_TYPES:
            raise FitCheckError(
                "UNSUPPORTED_UPLOAD_TYPE",
                "Use a JPG, PNG, or WebP outfit photo.",
                recommended_action="Convert HEIC photos to JPG before uploading.",
            )
        if payload.size_bytes is not None and payload.size_bytes > self.settings.max_upload_bytes:
            raise FitCheckError(
                "UPLOAD_TOO_LARGE",
                "This photo is larger than the private upload limit.",
                recommended_action=(
                    "Choose a photo no larger than "
                    f"{self.settings.max_upload_bytes // 1_048_576} MB."
                ),
            )

        user = await self._ensure_demo_user(session)
        upload_id = new_id()
        content_type = payload.content_type.lower()
        extension = _extension_for_upload(payload.filename, content_type)
        upload = Upload(
            id=upload_id,
            user_id=user.id,
            original_key=self.keys.upload_original(user.id, upload_id, extension),
            sha256=f"pending-{upload_id}",
            content_type=content_type,
            status="pending_upload",
            immutable_metadata={
                "filename": Path(payload.filename).name,
                "requested_content_type": content_type,
                "requested_size_bytes": payload.size_bytes,
            },
        )
        session.add(upload)
        await session.commit()

        if self.settings.storage_mode is StorageMode.LOCAL:
            return UploadPresignResponse(
                upload_id=upload.id,
                mode="api_proxy",
                upload_url=f"/v1/uploads/{upload.id}/content",
                original_key=upload.original_key,
            )

        signed_url = await self.storage.signed_upload_url(
            upload.original_key,
            content_type,
            self.settings.b2_presign_expires_seconds,
        )
        return UploadPresignResponse(
            upload_id=upload.id,
            mode="direct_b2",
            upload_url=signed_url,
            original_key=upload.original_key,
            expires_in_seconds=self.settings.b2_presign_expires_seconds,
        )

    async def receive_local_upload(
        self, session: AsyncSession, upload_id: str, content: bytes
    ) -> UploadFinalizeResponse:
        if self.settings.storage_mode is not StorageMode.LOCAL:
            raise FitCheckError(
                "LOCAL_UPLOAD_ENDPOINT_DISABLED",
                "This upload uses a private direct-storage URL instead.",
            )
        return await self._finalize_upload(session, upload_id, content, persist_original=True)

    async def create_import(
        self, session: AsyncSession, upload_ids: list[str]
    ) -> ImportJobResponse:
        user = await self._ensure_demo_user(session)
        resolved_uploads: list[Upload] = []
        for upload_id in dict.fromkeys(upload_ids):
            upload = await self._load_owned_upload(session, user.id, upload_id)
            if upload.status == "pending_upload":
                if self.settings.storage_mode is StorageMode.LOCAL:
                    raise FitCheckError(
                        "UPLOAD_NOT_COMPLETE",
                        "Finish saving this photo before starting its import.",
                        entity_id=upload.id,
                    )
                content = await self.storage.get_bytes(upload.original_key)
                finalized = await self._finalize_upload(
                    session, upload.id, content, persist_original=False
                )
                upload = await self._load_owned_upload(session, user.id, finalized.upload_id)
            if upload.status != ImportStatus.UPLOADED.value:
                raise FitCheckError(
                    "UPLOAD_NOT_READY",
                    "This photo is not ready for import.",
                    entity_id=upload.id,
                )
            resolved_uploads.append(upload)

        # Importing the exact same verified upload again must not start a
        # second candidate/generation path. Return its durable review job.
        existing_candidates = list(
            (
                await session.scalars(
                    select(GarmentCandidate).where(
                        GarmentCandidate.upload_id.in_([upload.id for upload in resolved_uploads]),
                        GarmentCandidate.import_job_id.is_not(None),
                    )
                )
            ).all()
        )
        existing_upload_ids = {candidate.upload_id for candidate in existing_candidates}
        existing_job_ids = {
            candidate.import_job_id
            for candidate in existing_candidates
            if candidate.import_job_id is not None
        }
        if len(existing_upload_ids) == len(resolved_uploads) and len(existing_job_ids) == 1:
            return await self.get_import(session, next(iter(existing_job_ids)))

        job = ImportJob(
            id=new_id(),
            user_id=user.id,
            status=ImportStatus.INVENTORYING.value,
            progress=10,
        )
        session.add(job)
        await session.flush()

        candidate_ids: list[str] = []
        errors: list[str] = []
        for upload in resolved_uploads:
            try:
                candidate = await self._create_candidate(session, user.id, upload, job.id)
            except FitCheckError as error:
                errors.append(f"{upload.id}: {error.code}")
                continue
            candidate_ids.append(candidate.id)

        job.progress = 100
        if candidate_ids:
            job.status = ImportStatus.AWAITING_REVIEW.value
            job.error_code = "PARTIAL_IMPORT" if errors else None
            job.error_message = "; ".join(errors) if errors else None
        else:
            job.status = ImportStatus.FAILED.value
            job.error_code = "IMPORT_FAILED"
            job.error_message = (
                "; ".join(errors) or "No reviewable garment candidates were created."
            )
        await session.commit()
        return await self.get_import(session, job.id)

    async def get_import(self, session: AsyncSession, job_id: str) -> ImportJobResponse:
        user = await self._ensure_demo_user(session)
        job = await session.scalar(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user.id)
        )
        if job is None:
            raise FitCheckError(
                "IMPORT_NOT_FOUND", "That import job is unavailable.", entity_id=job_id
            )
        candidates = list(
            (
                await session.scalars(
                    select(GarmentCandidate).where(GarmentCandidate.import_job_id == job.id)
                )
            ).all()
        )
        return ImportJobResponse(
            id=job.id,
            status=job.status,
            progress=job.progress,
            upload_ids=list(dict.fromkeys(candidate.upload_id for candidate in candidates)),
            candidate_ids=[candidate.id for candidate in candidates],
            candidate_count=len(candidates),
            error_code=job.error_code,
            error_message=job.error_message,
            stages=_import_stages(job.status),
        )

    async def list_candidates(
        self, session: AsyncSession, *, status: str | None = None
    ) -> list[CandidateResponse]:
        user = await self._ensure_demo_user(session)
        statement = (
            select(GarmentCandidate)
            .join(Upload, GarmentCandidate.upload_id == Upload.id)
            .where(Upload.user_id == user.id)
            .order_by(GarmentCandidate.created_at.desc())
        )
        if status:
            statement = statement.where(GarmentCandidate.status == status)
        candidates = list((await session.scalars(statement)).all())
        return [await self._candidate_response(candidate) for candidate in candidates]

    async def review_candidate(
        self,
        session: AsyncSession,
        candidate_id: str,
        payload: CandidateReviewRequest,
    ) -> CandidateResponse:
        user = await self._ensure_demo_user(session)
        candidate, upload = await self._load_owned_candidate(session, user.id, candidate_id)
        attributes = dict(candidate.attributes)

        if payload.action == "edit":
            _apply_candidate_fields(attributes, payload)
            candidate.attributes = attributes
            candidate.reviewer_notes = payload.notes or candidate.reviewer_notes
        elif payload.action == "reject":
            candidate.status = GarmentStatus.REJECTED.value
            candidate.reviewer_notes = payload.notes or "Rejected during human review."
        elif payload.action == "hold":
            candidate.status = GarmentStatus.NEEDS_BETTER_PHOTO.value
            candidate.reviewer_notes = (
                payload.notes or "Needs a clearer, front-facing garment photo."
            )
            candidate.unresolved_details = list(
                dict.fromkeys(
                    [
                        *candidate.unresolved_details,
                        "Capture the garment alone with visible edges and even light.",
                    ]
                )
            )
        else:
            if candidate.status not in {"awaiting_review", "edited"}:
                raise FitCheckError(
                    "CANDIDATE_NOT_APPROVABLE",
                    "Only an awaiting-review source crop can become a wardrobe item.",
                    entity_id=candidate.id,
                )
            _apply_candidate_fields(attributes, payload)
            if not candidate.source_crop_key:
                raise FitCheckError(
                    "SOURCE_EVIDENCE_MISSING",
                    "This candidate has no source crop to support approval.",
                    entity_id=candidate.id,
                )
            crop = await self.storage.head(candidate.source_crop_key)
            garment_id = new_id()
            garment = Garment(
                id=garment_id,
                user_id=user.id,
                name=str(attributes.get("name_suggestion") or "Unnamed wardrobe item"),
                category=str(attributes.get("category") or "top"),
                colors=_string_list(attributes.get("colors")),
                tags=_string_list(attributes.get("tags")),
                seasons=[],
                status=GarmentStatus.APPROVED.value,
                evidence_status=AssetEvidenceStatus.VERIFIED_SOURCE_BACKED.value,
                notes=payload.notes,
            )
            evidence = GarmentEvidence(
                id=new_id(),
                garment_id=garment_id,
                upload_id=upload.id,
                crop_key=candidate.source_crop_key,
                role="primary",
                notes="Immutable source crop approved by the user.",
                sha256=crop.sha256,
            )
            attributes["garment_id"] = garment_id
            candidate.attributes = attributes
            candidate.status = GarmentStatus.APPROVED.value
            candidate.reviewer_notes = payload.notes or "Approved from source-backed crop."
            session.add_all([garment, evidence])

        await session.commit()
        return await self._candidate_response(candidate)

    async def list_garments(
        self,
        session: AsyncSession,
        *,
        category: str | None = None,
        color: str | None = None,
        status: str | None = None,
        query: str | None = None,
    ) -> list[GarmentResponse]:
        user = await self._ensure_demo_user(session)
        statement = (
            select(Garment).where(Garment.user_id == user.id).order_by(Garment.created_at.desc())
        )
        if category:
            statement = statement.where(Garment.category == category)
        if status:
            statement = statement.where(Garment.status == status)
        else:
            # The closet/recommendation-facing collection contains only items
            # the user approved as inventory. M0's clearly labeled demo
            # reconstruction never leaks into owned wardrobe decisions.
            statement = statement.where(Garment.status == GarmentStatus.APPROVED.value)
        garments = list((await session.scalars(statement)).all())
        lowered_query = query.lower().strip() if query else ""
        lowered_color = color.lower().strip() if color else ""
        filtered = [
            garment
            for garment in garments
            if (not lowered_color or lowered_color in {value.lower() for value in garment.colors})
            and (
                not lowered_query
                or lowered_query in garment.name.lower()
                or lowered_query in garment.category.lower()
                or any(lowered_query in tag.lower() for tag in garment.tags)
            )
        ]
        return [await self._garment_response(session, garment) for garment in filtered]

    async def update_garment(
        self, session: AsyncSession, garment_id: str, payload: GarmentUpdateRequest
    ) -> GarmentResponse:
        user = await self._ensure_demo_user(session)
        garment = await session.scalar(
            select(Garment).where(Garment.id == garment_id, Garment.user_id == user.id)
        )
        if garment is None:
            raise FitCheckError(
                "GARMENT_NOT_FOUND", "That wardrobe item is unavailable.", entity_id=garment_id
            )
        for field in ("name", "category", "colors", "tags", "seasons", "purchase_date", "notes"):
            value = getattr(payload, field)
            if value is not None:
                setattr(garment, field, value)
        if payload.price is not None:
            garment.price = Decimal(str(payload.price))
        if payload.archive is True:
            garment.status = GarmentStatus.ARCHIVED.value
            garment.archived_at = datetime.now(UTC)
        await session.commit()
        return await self._garment_response(session, garment)

    async def _finalize_upload(
        self,
        session: AsyncSession,
        upload_id: str,
        content: bytes,
        *,
        persist_original: bool,
    ) -> UploadFinalizeResponse:
        if not content:
            raise FitCheckError("EMPTY_UPLOAD", "This photo is empty.")
        if len(content) > self.settings.max_upload_bytes:
            raise FitCheckError(
                "UPLOAD_TOO_LARGE",
                "This photo is larger than the private upload limit.",
                entity_id=upload_id,
            )
        user = await self._ensure_demo_user(session)
        upload = await self._load_owned_upload(session, user.id, upload_id)
        inspection = inspect_upload_image(content)
        source_hash = sha256_bytes(content)
        existing = await session.scalar(
            select(Upload).where(
                Upload.user_id == user.id,
                Upload.sha256 == source_hash,
                Upload.id != upload.id,
            )
        )
        if existing is not None:
            if persist_original:
                await session.delete(upload)
            else:
                upload.status = "duplicate"
                upload.immutable_metadata = {
                    **dict(upload.immutable_metadata),
                    "duplicate_of_upload_id": existing.id,
                    "calculated_sha256": source_hash,
                }
            await session.commit()
            return UploadFinalizeResponse(
                upload_id=existing.id,
                status=existing.status,
                duplicate=True,
                duplicate_of_upload_id=existing.id,
                sha256=existing.sha256,
                width=existing.width,
                height=existing.height,
                normalized_key=existing.normalized_key,
            )

        if persist_original:
            stored = await self.storage.put_bytes(
                upload.original_key,
                content,
                content_type=inspection.content_type,
                metadata={"upload-id": upload.id, "source-sha256": source_hash},
            )
            if stored.sha256 != source_hash:
                raise FitCheckError(
                    "STORAGE_HASH_MISMATCH",
                    "Saving securely failed validation.",
                    retryable=True,
                    entity_id=upload.id,
                )
        else:
            stored = await self.storage.head(upload.original_key)
            if stored.size != len(content):
                raise FitCheckError(
                    "STORAGE_VALIDATION_FAILED",
                    "Saving securely failed validation.",
                    retryable=True,
                    entity_id=upload.id,
                )

        normalized = normalize_image(content)
        normalized_key = self.keys.upload_normalized(user.id, upload.id)
        normalized_stored = await self.storage.put_bytes(
            normalized_key,
            normalized,
            content_type="image/jpeg",
            metadata={"upload-id": upload.id, "source-sha256": source_hash},
        )
        persisted_normalized = await self.storage.head(normalized_key)
        if persisted_normalized.sha256 != normalized_stored.sha256:
            raise FitCheckError(
                "STORAGE_HASH_MISMATCH",
                "Saving securely failed validation.",
                retryable=True,
                entity_id=upload.id,
            )
        upload.sha256 = source_hash
        upload.content_type = inspection.content_type
        upload.width = inspection.width
        upload.height = inspection.height
        upload.normalized_key = normalized_key
        upload.status = ImportStatus.UPLOADED.value
        upload.immutable_metadata = {
            **dict(upload.immutable_metadata),
            "sha256": source_hash,
            "normalized_sha256": normalized_stored.sha256,
            "image_format": inspection.image_format,
            "input_fingerprint": perceptual_input_fingerprint(content),
            "validated_at": datetime.now(UTC).isoformat(),
        }
        await session.commit()
        return UploadFinalizeResponse(
            upload_id=upload.id,
            status=upload.status,
            sha256=upload.sha256,
            width=upload.width,
            height=upload.height,
            normalized_key=upload.normalized_key,
        )

    async def _create_candidate(
        self, session: AsyncSession, user_id: str, upload: Upload, job_id: str
    ) -> GarmentCandidate:
        existing = await session.scalar(
            select(GarmentCandidate).where(
                GarmentCandidate.upload_id == upload.id,
                GarmentCandidate.status != GarmentStatus.REJECTED.value,
            )
        )
        if existing is not None:
            return existing
        if upload.normalized_key is None or upload.width is None or upload.height is None:
            raise FitCheckError(
                "UPLOAD_NOT_NORMALIZED",
                "This photo is missing its normalized review copy.",
                entity_id=upload.id,
            )
        normalized = await self.storage.get_bytes(upload.normalized_key)
        candidate_id = new_id()
        source_crop_key = self.keys.candidate_source_crop(user_id, upload.id, candidate_id)
        crop = crop_normalized_image(
            normalized,
            left=0,
            top=0,
            right=upload.width,
            bottom=upload.height,
        )
        crop_stored = await self.storage.put_bytes(
            source_crop_key,
            crop,
            content_type="image/jpeg",
            metadata={"upload-id": upload.id, "candidate-id": candidate_id, "role": "source-crop"},
        )
        color = approximate_color_name(crop)
        candidate = GarmentCandidate(
            id=candidate_id,
            upload_id=upload.id,
            import_job_id=job_id,
            bbox={
                "left": 0.0,
                "top": 0.0,
                "right": float(upload.width),
                "bottom": float(upload.height),
            },
            attributes={
                "name_suggestion": f"{color.title()} top",
                "category": "top",
                "colors": [color],
                "tags": [],
                "apparent_material": "needs review",
                "pattern": "needs review",
                "source_crop_sha256": crop_stored.sha256,
                "source_fingerprint": perceptual_input_fingerprint(crop),
            },
            unresolved_details=[
                "Confirm the garment boundary before creating a catalog cutout.",
                "Material and pattern are intentionally left for human review.",
            ],
            confidence=0.55,
            status="awaiting_review",
            source_crop_key=source_crop_key,
        )
        session.add(candidate)
        await session.flush()
        return candidate

    async def _candidate_response(self, candidate: GarmentCandidate) -> CandidateResponse:
        crop_url = (
            await self.storage.signed_read_url(candidate.source_crop_key)
            if candidate.source_crop_key
            else None
        )
        attributes = dict(candidate.attributes)
        return CandidateResponse(
            id=candidate.id,
            upload_id=candidate.upload_id,
            import_job_id=candidate.import_job_id,
            bbox={key: float(value) for key, value in candidate.bbox.items()},
            attributes=attributes,
            unresolved_details=list(candidate.unresolved_details),
            confidence=float(candidate.confidence),
            status=candidate.status,
            source_crop_key=candidate.source_crop_key,
            source_crop_url=crop_url,
            reviewer_notes=candidate.reviewer_notes,
            garment_id=_optional_string(attributes.get("garment_id")),
            created_at=candidate.created_at,
        )

    async def _garment_response(self, session: AsyncSession, garment: Garment) -> GarmentResponse:
        evidence = await session.scalar(
            select(GarmentEvidence)
            .where(GarmentEvidence.garment_id == garment.id)
            .order_by(GarmentEvidence.created_at.asc())
        )
        source_crop_key = evidence.crop_key if evidence else None
        source_crop_url = (
            await self.storage.signed_read_url(source_crop_key) if source_crop_key else None
        )
        return GarmentResponse(
            id=garment.id,
            name=garment.name,
            category=garment.category,
            colors=list(garment.colors),
            tags=list(garment.tags),
            seasons=list(garment.seasons),
            price=float(garment.price) if garment.price is not None else None,
            purchase_date=garment.purchase_date,
            notes=garment.notes,
            wear_count=garment.wear_count,
            status=garment.status,
            evidence_status=garment.evidence_status,
            source_crop_key=source_crop_key,
            source_crop_url=source_crop_url,
            canonical_asset_id=garment.canonical_asset_id,
            created_at=garment.created_at,
        )

    async def _ensure_demo_user(self, session: AsyncSession) -> User:
        user = await session.scalar(select(User).where(User.id == self.settings.demo_user_id))
        if user is not None:
            return user
        user = User(
            id=self.settings.demo_user_id,
            auth_subject="demo:local-owner",
            display_name="Fit Check local owner",
            default_location="New York, NY",
        )
        session.add(user)
        await session.flush()
        return user

    async def _load_owned_upload(
        self, session: AsyncSession, user_id: str, upload_id: str
    ) -> Upload:
        upload = await session.scalar(
            select(Upload).where(Upload.id == upload_id, Upload.user_id == user_id)
        )
        if upload is None:
            raise FitCheckError(
                "UPLOAD_NOT_FOUND", "That upload is unavailable.", entity_id=upload_id
            )
        return upload

    async def _load_owned_candidate(
        self, session: AsyncSession, user_id: str, candidate_id: str
    ) -> tuple[GarmentCandidate, Upload]:
        row = await session.execute(
            select(GarmentCandidate, Upload)
            .join(Upload, GarmentCandidate.upload_id == Upload.id)
            .where(GarmentCandidate.id == candidate_id, Upload.user_id == user_id)
        )
        candidate, upload = row.one_or_none() or (None, None)
        if candidate is None or upload is None:
            raise FitCheckError(
                "CANDIDATE_NOT_FOUND",
                "That review candidate is unavailable.",
                entity_id=candidate_id,
            )
        return candidate, upload


def _extension_for_upload(filename: str, content_type: str) -> str:
    extension = Path(filename).suffix.lower().lstrip(".")
    safe_extensions = {"jpg", "jpeg", "png", "webp"}
    if extension not in safe_extensions:
        return _EXTENSIONS_BY_CONTENT_TYPE[content_type]
    if content_type == "image/jpeg" and extension == "jpeg":
        return "jpg"
    return extension


def _apply_candidate_fields(attributes: dict[str, Any], payload: CandidateReviewRequest) -> None:
    if payload.name is not None:
        attributes["name_suggestion"] = payload.name.strip()
    if payload.category is not None:
        attributes["category"] = payload.category.strip().lower()
    if payload.colors is not None:
        attributes["colors"] = _string_list(payload.colors)
    if payload.tags is not None:
        attributes["tags"] = _string_list(payload.tags)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _optional_string(value: object) -> str | None:
    return str(value) if isinstance(value, str) else None


def _import_stages(status: str) -> list[str]:
    ordered = [
        ImportStatus.UPLOADED.value,
        ImportStatus.INVENTORYING.value,
        ImportStatus.AWAITING_REVIEW.value,
        ImportStatus.EXTRACTING.value,
        ImportStatus.QUALITY_CHECK.value,
        ImportStatus.COMPLETE.value,
    ]
    if status == ImportStatus.FAILED.value:
        return [*ordered[:2], ImportStatus.FAILED.value]
    try:
        index = ordered.index(status)
    except ValueError:
        return [status]
    return ordered[: index + 1]
