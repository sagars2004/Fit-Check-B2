from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app_env: str
    provider_mode: str
    storage_mode: str
    gmi_model_configured: bool


class MockPipelineRequest(BaseModel):
    garment_name: str = Field(default="Demo navy overshirt", min_length=2, max_length=100)
    parent_run_id: str | None = None


class DemoAssetResponse(BaseModel):
    asset_id: str
    garment_id: str
    run_id: str
    parent_run_id: str | None
    object_key: str
    sha256: str
    manifest_key: str
    manifest_hash: str
    evidence_status: str
    provider: str
    model: str
    created_at: datetime


class ProvenanceResponse(BaseModel):
    entity_type: str
    entity_id: str
    manifest: dict[str, Any]


class UploadPresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    size_bytes: int | None = Field(default=None, ge=1, le=104_857_600)


class UploadPresignResponse(BaseModel):
    upload_id: str
    mode: Literal["api_proxy", "direct_b2"]
    upload_url: str
    original_key: str
    expires_in_seconds: int | None = None
    duplicate: bool = False


class UploadFinalizeResponse(BaseModel):
    upload_id: str
    status: str
    duplicate: bool = False
    duplicate_of_upload_id: str | None = None
    sha256: str
    width: int | None = None
    height: int | None = None
    normalized_key: str | None = None


class ImportCreateRequest(BaseModel):
    upload_ids: list[str] = Field(min_length=1, max_length=20)


class ImportJobResponse(BaseModel):
    id: str
    status: str
    progress: int
    upload_ids: list[str]
    candidate_ids: list[str] = Field(default_factory=list)
    candidate_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    stages: list[str]


class CandidateReviewRequest(BaseModel):
    action: Literal["approve", "edit", "reject", "hold"]
    name: str | None = Field(default=None, min_length=1, max_length=180)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    colors: list[str] | None = Field(default=None, max_length=8)
    tags: list[str] | None = Field(default=None, max_length=16)
    notes: str | None = Field(default=None, max_length=2_000)


class CandidateResponse(BaseModel):
    id: str
    upload_id: str
    import_job_id: str | None
    bbox: dict[str, float]
    attributes: dict[str, Any]
    unresolved_details: list[str]
    confidence: float
    status: str
    source_crop_key: str | None
    source_crop_url: str | None = None
    reviewer_notes: str | None
    garment_id: str | None = None
    created_at: datetime


class GarmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    colors: list[str] | None = Field(default=None, max_length=8)
    tags: list[str] | None = Field(default=None, max_length=16)
    seasons: list[str] | None = Field(default=None, max_length=8)
    price: float | None = Field(default=None, ge=0, le=1_000_000)
    purchase_date: date | None = None
    notes: str | None = Field(default=None, max_length=2_000)
    archive: bool | None = None


class GarmentResponse(BaseModel):
    id: str
    name: str
    category: str
    colors: list[str]
    tags: list[str]
    seasons: list[str]
    price: float | None
    purchase_date: date | None
    notes: str | None
    wear_count: int
    status: str
    evidence_status: str
    source_crop_key: str | None = None
    source_crop_url: str | None = None
    canonical_asset_id: str | None = None
    created_at: datetime
