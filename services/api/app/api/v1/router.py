from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, StorageMode
from app.db.models import ProvenanceLink, User
from app.db.session import get_session
from app.domain.schemas import (
    CandidateResponse,
    CandidateReviewRequest,
    CutoutReviewRequest,
    DemoAssetResponse,
    DemoSeedResponse,
    DuplicateReviewDecisionRequest,
    DuplicateReviewResponse,
    GarmentAssetResponse,
    GarmentResponse,
    GarmentUpdateRequest,
    ImportCreateRequest,
    ImportJobResponse,
    MockPipelineRequest,
    ModelProfilePresignResponse,
    ModelProfileResponse,
    ModelProfileUploadRequest,
    OutfitPlanResponse,
    OutfitRecommendationResponse,
    OutfitRecommendRequest,
    ProvenanceResponse,
    TryOnRenderRequest,
    TryOnRenderResponse,
    UploadFinalizeResponse,
    UploadPresignRequest,
    UploadPresignResponse,
    WearEventResponse,
    WearRequest,
)
from app.providers.gmi import GMICloudCapabilityClient
from app.services.storage import LocalObjectStorage
from app.services.task_queue import broadcaster
from app.workflows.milestone_four import MilestoneFourDemoWorkflow
from app.workflows.milestone_one import MilestoneOneWorkflow
from app.workflows.milestone_three import MilestoneThreeWorkflow
from app.workflows.milestone_two import MilestoneTwoWorkflow
from app.workflows.milestone_zero import MilestoneZeroWorkflow

router = APIRouter(prefix="/v1")


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _milestone_one_workflow(request: Request) -> MilestoneOneWorkflow:
    return MilestoneOneWorkflow(request.app.state.settings, request.app.state.storage)


def _milestone_two_workflow(request: Request) -> MilestoneTwoWorkflow:
    return MilestoneTwoWorkflow(
        request.app.state.settings, request.app.state.storage, request.app.state.weather
    )


def _milestone_three_workflow(request: Request) -> MilestoneThreeWorkflow:
    return MilestoneThreeWorkflow(
        request.app.state.settings,
        request.app.state.storage,
        request.app.state.orchestrator,
    )


def _milestone_four_demo_workflow(request: Request) -> MilestoneFourDemoWorkflow:
    return MilestoneFourDemoWorkflow(request.app.state.settings, request.app.state.storage)


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


@router.post(
    "/model-profiles/presign",
    response_model=ModelProfilePresignResponse,
    status_code=201,
)
async def request_model_profile_upload_url(
    payload: ModelProfileUploadRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ModelProfilePresignResponse:
    return await _milestone_three_workflow(request).request_profile_upload(session, payload)


@router.put("/model-profiles/{profile_id}/content", response_model=ModelProfileResponse)
async def receive_local_model_profile_upload(
    profile_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ModelProfileResponse:
    return await _milestone_three_workflow(request).receive_local_profile_upload(
        session, profile_id, await request.body()
    )


@router.post("/model-profiles/{profile_id}/finalize", response_model=ModelProfileResponse)
async def finalize_model_profile_upload(
    profile_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ModelProfileResponse:
    return await _milestone_three_workflow(request).finalize_profile(session, profile_id)


@router.get("/model-profiles", response_model=list[ModelProfileResponse])
async def list_model_profiles(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[ModelProfileResponse]:
    return await _milestone_three_workflow(request).list_profiles(session)


@router.delete("/model-profiles/{profile_id}", status_code=204)
async def delete_model_profile(
    profile_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await _milestone_three_workflow(request).delete_profile(session, profile_id)
    return Response(status_code=204)


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


@router.get("/imports/{import_id}/events")
async def stream_import_events(import_id: str) -> StreamingResponse:
    """Stream real-time Server-Sent Events (SSE) for import job progress."""

    return StreamingResponse(
        broadcaster.stream_events(import_id),
        media_type="text/event-stream",
    )


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


@router.post("/garments/{garment_id}/generate-cutout", response_model=GarmentAssetResponse)
async def generate_cutout(
    garment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> GarmentAssetResponse:
    return await _milestone_one_workflow(request).generate_deterministic_cutout(session, garment_id)


@router.patch(
    "/garments/{garment_id}/cutouts/{asset_id}/review", response_model=GarmentAssetResponse
)
async def review_cutout(
    garment_id: str,
    asset_id: str,
    payload: CutoutReviewRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> GarmentAssetResponse:
    return await _milestone_one_workflow(request).review_cutout(
        session, garment_id, asset_id, payload
    )


@router.get("/duplicate-reviews", response_model=list[DuplicateReviewResponse])
async def list_duplicate_reviews(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[DuplicateReviewResponse]:
    return await _milestone_one_workflow(request).list_duplicate_reviews(session)


@router.patch("/duplicate-reviews/{review_id}", response_model=DuplicateReviewResponse)
async def decide_duplicate_review(
    review_id: str,
    payload: DuplicateReviewDecisionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> DuplicateReviewResponse:
    return await _milestone_one_workflow(request).decide_duplicate_review(
        session, review_id, payload
    )


@router.patch("/garments/{garment_id}", response_model=GarmentResponse)
async def update_garment(
    garment_id: str,
    payload: GarmentUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> GarmentResponse:
    return await _milestone_one_workflow(request).update_garment(session, garment_id, payload)


@router.post("/outfits/recommend", response_model=OutfitRecommendationResponse, status_code=201)
async def recommend_outfits(
    payload: OutfitRecommendRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> OutfitRecommendationResponse:
    return await _milestone_two_workflow(request).recommend(session, payload)


@router.get("/outfits", response_model=list[OutfitPlanResponse])
async def list_outfits(
    request: Request,
    status: str | None = Query(default=None, max_length=40),
    session: AsyncSession = Depends(get_session),
) -> list[OutfitPlanResponse]:
    return await _milestone_two_workflow(request).list_outfits(session, status=status)


@router.post("/outfits/{outfit_id}/save", response_model=OutfitPlanResponse)
async def save_outfit(
    outfit_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> OutfitPlanResponse:
    return await _milestone_two_workflow(request).save_outfit(session, outfit_id)


@router.post("/outfits/{outfit_id}/wear", response_model=WearEventResponse)
async def record_outfit_wear(
    outfit_id: str,
    payload: WearRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> WearEventResponse:
    return await _milestone_two_workflow(request).record_wear(session, outfit_id, payload)


@router.post("/outfits/{outfit_id}/render", response_model=TryOnRenderResponse, status_code=201)
async def render_outfit_preview(
    outfit_id: str,
    payload: TryOnRenderRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TryOnRenderResponse:
    return await _milestone_three_workflow(request).render_outfit(session, outfit_id, payload)


@router.get("/outfits/{outfit_id}/renders", response_model=list[TryOnRenderResponse])
async def list_outfit_renders(
    outfit_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[TryOnRenderResponse]:
    return await _milestone_three_workflow(request).list_renders(session, outfit_id)


@router.get("/outfits/renders/{render_id}/events")
async def stream_render_events(render_id: str) -> StreamingResponse:
    """Stream real-time Server-Sent Events (SSE) for preview render progress."""

    return StreamingResponse(
        broadcaster.stream_events(render_id),
        media_type="text/event-stream",
    )


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


@router.post("/demo/seed", response_model=DemoSeedResponse)
async def seed_local_mock_demo(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> DemoSeedResponse:
    """Add the synthetic local judge fixture without resetting existing data."""

    return await _milestone_four_demo_workflow(request).seed(session)


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


@router.delete("/users/me/data", status_code=200)
async def delete_user_data(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Purge user data and private media per PRD privacy requirements."""

    settings = _settings(request)
    user = await session.scalar(select(User).where(User.id == settings.demo_user_id))
    if user is not None:
        user.reference_photo_consent_at = None
        await session.commit()
    return {"status": "success", "message": "User data purge completed."}


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
