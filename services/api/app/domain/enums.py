from enum import StrEnum


class GarmentStatus(StrEnum):
    CANDIDATE = "candidate"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    GENERATING = "generating"
    QA_REVIEW = "qa_review"
    READY = "ready"
    NEEDS_BETTER_PHOTO = "needs_better_photo"
    DUPLICATE_PENDING = "duplicate_pending"
    ARCHIVED = "archived"
    DELETED = "deleted"


class AssetEvidenceStatus(StrEnum):
    VERIFIED_SOURCE_BACKED = "verified_source_backed"
    AI_RECONSTRUCTED = "ai_reconstructed"
    NEEDS_BETTER_PHOTO = "needs_better_photo"


class ImportStatus(StrEnum):
    UPLOADED = "uploaded"
    INVENTORYING = "inventorying"
    AWAITING_REVIEW = "awaiting_review"
    EXTRACTING = "extracting"
    QUALITY_CHECK = "quality_check"
    COMPLETE = "complete"
    FAILED = "failed"


class OutfitStatus(StrEnum):
    PROPOSED = "proposed"
    SAVED = "saved"
    PREVIEW_GENERATING = "preview_generating"
    PREVIEW_READY = "preview_ready"
    WORN = "worn"
    REJECTED = "rejected"

