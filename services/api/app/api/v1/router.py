from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, StorageMode
from app.db.models import ProvenanceLink
from app.db.session import get_session
from app.domain.schemas import DemoAssetResponse, MockPipelineRequest, ProvenanceResponse
from app.providers.gmi import GMICloudCapabilityClient
from app.services.storage import LocalObjectStorage
from app.workflows.milestone_zero import MilestoneZeroWorkflow

router = APIRouter(prefix="/v1")


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.post("/demo/mock-cutout", response_model=DemoAssetResponse, status_code=201)
async def create_mock_cutout(
    payload: MockPipelineRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> DemoAssetResponse:
    workflow = MilestoneZeroWorkflow(
        request.app.state.settings,
        request.app.state.storage,
        request.app.state.orchestrator,
    )
    return await workflow.create_demo_cutout(
        session,
        garment_name=payload.garment_name,
        parent_run_id=payload.parent_run_id,
    )


@router.get("/provenance/{entity_type}/{entity_id}", response_model=ProvenanceResponse)
async def get_provenance(
    entity_type: str,
    entity_id: str,
    session: AsyncSession = Depends(get_session),
) -> ProvenanceResponse:
    link = await session.scalar(
        select(ProvenanceLink).where(
            ProvenanceLink.entity_type == entity_type,
            ProvenanceLink.entity_id == entity_id,
            ProvenanceLink.deleted_at.is_(None),
        )
    )
    if link is None:
        raise HTTPException(status_code=404, detail="No provenance record exists for this asset.")
    # M0 has a single demo user. Auth-aware owner/shared redaction is added with
    # onboarding in M1; this stored representation contains no signed URLs.
    return ProvenanceResponse(
        entity_type=entity_type,
        entity_id=entity_id,
        manifest=link.redacted_manifest,
    )


@router.post("/system/gmi-capability-smoke-test")
async def gmi_capability_smoke_test(request: Request) -> dict[str, object]:
    settings = _settings(request)
    return await GMICloudCapabilityClient(settings).smoke_test()


@router.get("/media/{object_key:path}")
async def get_local_mock_media(object_key: str, request: Request) -> Response:
    settings = _settings(request)
    storage = request.app.state.storage
    if settings.storage_mode is not StorageMode.LOCAL or not settings.is_mock:
        raise HTTPException(status_code=404, detail="Not found.")
    if not isinstance(storage, LocalObjectStorage):
        raise HTTPException(status_code=404, detail="Not found.")
    content = await storage.get_bytes(object_key)
    stored = await storage.head(object_key)
    return Response(content=content, media_type=stored.content_type)
