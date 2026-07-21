from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    auth_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    default_location: Mapped[str | None] = mapped_column(String(255))
    reference_photo_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelProfile(TimestampMixin, Base):
    __tablename__ = "model_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_image_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Upload(TimestampMixin, Base):
    __tablename__ = "uploads"
    __table_args__ = (UniqueConstraint("user_id", "sha256", name="uq_uploads_user_sha256"), Index("ix_uploads_user_status", "user_id", "status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    normalized_key: Mapped[str | None] = mapped_column(String(1024))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    source_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="uploaded", nullable=False)
    immutable_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (Index("ix_import_jobs_user_status", "user_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="uploaded", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(String(255))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class GarmentCandidate(TimestampMixin, Base):
    __tablename__ = "garment_candidates"
    __table_args__ = (Index("ix_candidates_upload_status", "upload_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    upload_id: Mapped[str] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    import_job_id: Mapped[str | None] = mapped_column(ForeignKey("import_jobs.id", ondelete="SET NULL"))
    bbox: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    unresolved_details: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="awaiting_review", nullable=False)
    source_crop_key: Mapped[str | None] = mapped_column(String(1024))
    reviewer_notes: Mapped[str | None] = mapped_column(Text)


class Garment(TimestampMixin, Base):
    __tablename__ = "garments"
    __table_args__ = (Index("ix_garments_user_status", "user_id", "status"), Index("ix_garments_user_category", "user_id", "category"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    colors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    seasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    wear_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="approved", nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(40), default="verified_source_backed", nullable=False)
    canonical_asset_id: Mapped[str | None] = mapped_column(String(36))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GarmentEvidence(TimestampMixin, Base):
    __tablename__ = "garment_evidence"
    __table_args__ = (Index("ix_garment_evidence_garment", "garment_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    garment_id: Mapped[str] = mapped_column(ForeignKey("garments.id", ondelete="CASCADE"), nullable=False)
    upload_id: Mapped[str | None] = mapped_column(ForeignKey("uploads.id", ondelete="SET NULL"))
    crop_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="primary", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))


class GarmentAsset(TimestampMixin, Base):
    __tablename__ = "garment_assets"
    __table_args__ = (UniqueConstraint("garment_id", "kind", "version", name="uq_garment_asset_version"), Index("ix_garment_assets_garment_kind", "garment_id", "kind"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    garment_id: Mapped[str] = mapped_column(ForeignKey("garments.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    qa_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    qa_warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(40), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(255))
    parent_run_id: Mapped[str | None] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DuplicateReview(TimestampMixin, Base):
    __tablename__ = "duplicate_reviews"
    __table_args__ = (UniqueConstraint("garment_a_id", "garment_b_id", name="uq_duplicate_pair"), Index("ix_duplicate_reviews_status", "status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    garment_a_id: Mapped[str] = mapped_column(ForeignKey("garments.id", ondelete="CASCADE"), nullable=False)
    garment_b_id: Mapped[str] = mapped_column(ForeignKey("garments.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    reviewer_notes: Mapped[str | None] = mapped_column(Text)


class OutfitPlan(TimestampMixin, Base):
    __tablename__ = "outfit_plans"
    __table_args__ = (Index("ix_outfit_plans_user_status", "user_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weather_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occasion: Mapped[str] = mapped_column(String(500), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="proposed", nullable=False)
    planner_run_id: Mapped[str | None] = mapped_column(String(255))


class OutfitItem(TimestampMixin, Base):
    __tablename__ = "outfit_items"
    __table_args__ = (UniqueConstraint("outfit_id", "garment_id", name="uq_outfit_garment"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    outfit_id: Mapped[str] = mapped_column(ForeignKey("outfit_plans.id", ondelete="CASCADE"), nullable=False)
    garment_id: Mapped[str] = mapped_column(ForeignKey("garments.id", ondelete="RESTRICT"), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)


class TryOnRender(TimestampMixin, Base):
    __tablename__ = "tryon_renders"
    __table_args__ = (Index("ix_tryon_renders_outfit_status", "outfit_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    outfit_id: Mapped[str] = mapped_column(ForeignKey("outfit_plans.id", ondelete="CASCADE"), nullable=False)
    profile_id: Mapped[str] = mapped_column(ForeignKey("model_profiles.id", ondelete="RESTRICT"), nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(1024))
    sha256: Mapped[str | None] = mapped_column(String(64))
    run_id: Mapped[str | None] = mapped_column(String(255))
    parent_run_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="preview_generating", nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(255))
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)


class WearEvent(TimestampMixin, Base):
    __tablename__ = "wear_events"
    __table_args__ = (Index("ix_wear_events_user_worn_on", "user_id", "worn_on"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    outfit_id: Mapped[str | None] = mapped_column(ForeignKey("outfit_plans.id", ondelete="SET NULL"))
    worn_on: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_reason: Mapped[str | None] = mapped_column(Text)


class ProvenanceLink(TimestampMixin, Base):
    __tablename__ = "provenance_links"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="uq_provenance_entity"), Index("ix_provenance_links_run_id", "run_id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    manifest_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(255))
    privacy_scope: Mapped[str] = mapped_column(String(40), default="private", nullable=False)
    redacted_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

