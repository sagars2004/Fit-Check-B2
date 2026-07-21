from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, StorageMode
from app.db.models import ProvenanceLink
from app.db.session import get_session
from app.domain.schemas import (
    CandidateResponse,
    CandidateReviewRequest,
    DemoAssetResponse,
    GarmentResponse,
    GarmentUpdateRequest,
    ImportCreateRequest,
    ImportJobResponse,
    MockPipelineRequest,
    ProvenanceResponse,
    UploadFinalizeResponse,
    UploadPresignRequest,
    UploadPresignResponse,
)
from app.providers.gmi import GMICloudCapabilityClient
from app.services.storage import LocalObjectStorage
from app.workflows.milestone_one import MilestoneOneWorkflow
from app.workflows.milestone_zero import MilestoneZeroWorkflow

router = APIRouter(prefix="/v1")


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _milestone_one_workflow(request: Request) -> MilestoneOneWorkflow:
    return MilestoneOneWorkflow(request.app.state.settings, request.app.state.storage)


@router.post("/uploads/presign", response_model=UploadPresignResponse, status_code=201)
async def request_upload_url(
    payload: UploadPresignRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UploadPresignResponse:
    """Issue a server-generated, tenant-scoped upload target.

    Mock mode intentionally returns an API-only path. Live B2 mode returns a
    short-lived, exact-object presign and never exposes B2 credentials.
    """

    return await _milestone_one_workflow(request).request_upload(session, payload)


@router.put("/uploads/{upload_id}/content", response_model=UploadFinalizeResponse)
async def receive_local_upload(
    upload_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UploadFinalizeResponse:
    return await _milestone_one_workflow(request).receive_local_upload(
        session, upload_id, await request.body()
    )


@router.post("/imports", response_model=ImportJobResponse, status_code=201)
async def create_import(
    payload: ImportCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ImportJobResponse:
    return await _milestone_one_workflow(request).create_import(session, payload.upload_ids)


@router.get("/imports/{import_id}", response_model=ImportJobResponse)
async def get_import(
    import_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ImportJobResponse:
    return await _milestone_one_workflow(request).get_import(session, import_id)


@router.get("/candidates", response_model=list[CandidateResponse])
@router.get("/garment-candidates", response_model=list[CandidateResponse], include_in_schema=False)
async def list_candidates(
    request: Request,
    status: str | None = Query(default=None, max_length=40),
    session: AsyncSession = Depends(get_session),
) -> list[CandidateResponse]:
    return await _milestone_one_workflow(request).list_candidates(session, status=status)


@router.patch("/candidates/{candidate_id}", response_model=CandidateResponse)
@router.patch(
    "/garment-candidates/{candidate_id}/review",
    response_model=CandidateResponse,
    include_in_schema=False,
)
async def review_candidate(
    candidate_id: str,
    payload: CandidateReviewRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CandidateResponse:
    return await _milestone_one_workflow(request).review_candidate(session, candidate_id, payload)


@router.get("/garments", response_model=list[GarmentResponse])
async def list_garments(
    request: Request,
    category: str | None = Query(default=None, max_length=80),
    color: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=180),
    session: AsyncSession = Depends(get_session),
) -> list[GarmentResponse]:
    return await _milestone_one_workflow(request).list_garments(
        session, category=category, color=color, status=status, query=q
    )


@router.patch("/garments/{garment_id}", response_model=GarmentResponse)
async def update_garment(
    garment_id: str,
    payload: GarmentUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> GarmentResponse:
    return await _milestone_one_workflow(request).update_garment(session, garment_id, payload)


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
    # The local MVP has one resolved demo owner. This stored representation
    # contains no signed URLs; real owner/shared authorization lands with auth.
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
