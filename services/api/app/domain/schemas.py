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


class DemoSeedGarmentResponse(BaseModel):
    """A synthetic fixture item returned by the local demo seed endpoint."""

    id: str
    name: str
    category: str
    status: str
    evidence_status: str


class DemoSeedResponse(BaseModel):
    """Non-destructive local mock data prepared for the judge demo flow."""

    mode: Literal["local_mock"]
    fixture_version: str
    created: bool
    disclosure: str
    garments: list[DemoSeedGarmentResponse]
    fixture_garment_ids: list[str]
    approved_garment_ids: list[str]
    needs_better_photo_garment_id: str
    approved_garment_count: int
    fixture_garment_count: int
    profile_seeded: Literal[False] = False
    reference_photo_requirement: str


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


class ModelProfileUploadRequest(BaseModel):
    """Request a private reference-image target after explicit consent."""

    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    size_bytes: int | None = Field(default=None, ge=1, le=104_857_600)
    consent: bool = False


class ModelProfilePresignResponse(BaseModel):
    profile_id: str
    mode: Literal["api_proxy", "direct_b2"]
    upload_url: str
    source_image_key: str
    expires_in_seconds: int | None = None


class ModelProfileResponse(BaseModel):
    id: str
    status: str
    source_image_key: str
    source_image_url: str | None = None
    sha256: str | None = None
    consented_at: datetime
    created_at: datetime


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


class GarmentAssetResponse(BaseModel):
    id: str
    kind: str
    object_key: str
    asset_url: str | None = None
    sha256: str
    version: int
    qa_status: str
    qa_warnings: list[str]
    evidence_status: str
    run_id: str | None
    parent_run_id: str | None
    provider: str
    model: str
    approved_at: datetime | None
    created_at: datetime


class CutoutReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    notes: str | None = Field(default=None, max_length=2_000)


class DuplicateGarmentReference(BaseModel):
    id: str
    name: str
    category: str
    colors: list[str]
    source_crop_url: str | None = None
    cutout_url: str | None = None


class DuplicateReviewResponse(BaseModel):
    id: str
    score: float
    evidence: dict[str, Any]
    status: str
    reviewer_notes: str | None
    garment_a: DuplicateGarmentReference
    garment_b: DuplicateGarmentReference
    created_at: datetime


class DuplicateReviewDecisionRequest(BaseModel):
    action: Literal["keep_separate", "mark_likely_duplicate"]
    notes: str | None = Field(default=None, max_length=2_000)


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
    cutouts: list[GarmentAssetResponse] = Field(default_factory=list)
    created_at: datetime


class WeatherSnapshotResponse(BaseModel):
    location: str
    forecast_date: date
    low_c: float
    high_c: float
    apparent_high_c: float
    precipitation_probability: int
    precipitation_mm: float
    weather_code: int
    wind_kph: float
    condition: str
    source: str
    advisory: str | None = None


class OutfitRecommendRequest(BaseModel):
    location: str | None = Field(default=None, min_length=2, max_length=255)
    forecast_date: date = Field(default_factory=date.today)
    occasion: str = Field(default="Everyday", min_length=2, max_length=500)
    utilization_mode: bool = False


class OutfitItemResponse(BaseModel):
    garment_id: str
    role: str
    name: str
    category: str
    colors: list[str]
    tags: list[str]
    wear_count: int
    price: float | None
    cost_per_wear: float | None = None
    evidence_status: str
    image_url: str | None = None


class OutfitPlanResponse(BaseModel):
    id: str
    title: str
    weather: WeatherSnapshotResponse
    occasion: str
    score: float
    reasoning: str
    status: str
    planner_run_id: str | None
    items: list[OutfitItemResponse]
    created_at: datetime


class OutfitRecommendationResponse(BaseModel):
    weather: WeatherSnapshotResponse
    occasion: str
    options: list[OutfitPlanResponse]
    warnings: list[str] = Field(default_factory=list)


class WearRequest(BaseModel):
    action: Literal["wear", "undo"] = "wear"
    worn_on: date = Field(default_factory=date.today)
    notes: str | None = Field(default=None, max_length=2_000)


class WearEventResponse(BaseModel):
    event_id: str
    outfit_id: str
    action: Literal["wear", "undo"]
    worn_on: date
    outfit_status: str
    garment_wear_counts: dict[str, int]
    garment_cost_per_wear: dict[str, float | None]


class TryOnRenderRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=36)
    parent_run_id: str | None = Field(default=None, min_length=1, max_length=255)
    correction_hint: str | None = Field(default=None, min_length=1, max_length=500)


class TryOnSourceGarmentResponse(BaseModel):
    id: str
    name: str
    category: str
    colors: list[str]
    evidence_status: str
    source_kind: str
    image_url: str | None = None


class TryOnRenderResponse(BaseModel):
    id: str
    outfit_id: str
    profile_id: str
    status: str
    object_key: str | None = None
    render_url: str | None = None
    sha256: str | None = None
    run_id: str | None = None
    parent_run_id: str | None = None
    provider: str | None = None
    model: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    source_garment_ids: list[str]
    source_garments: list[TryOnSourceGarmentResponse]
    reference_image_url: str | None = None
    disclosure: str
    provenance_entity_type: Literal["tryon_render"] = "tryon_render"
    created_at: datetime
