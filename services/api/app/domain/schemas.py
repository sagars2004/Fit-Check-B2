from __future__ import annotations

from datetime import datetime
from typing import Any

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

