from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings
from app.core.errors import FitCheckError
from app.db.session import Database
from app.domain.schemas import HealthResponse
from app.providers.factory import build_media_orchestrator
from app.services.storage import build_storage
from app.services.weather import WeatherService


def create_app(runtime_settings: Settings | None = None) -> FastAPI:
    settings = runtime_settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=settings.log_level)
        database = Database(settings)
        if settings.auto_create_schema:
            await database.initialize()

        app.state.settings = settings
        app.state.database = database
        app.state.storage = build_storage(settings)
        app.state.orchestrator = build_media_orchestrator(settings)
        app.state.weather = WeatherService(settings)
        yield
        await database.dispose()

    application = FastAPI(
        title="Fit Check API",
        version="0.1.0",
        description="Private wardrobe media orchestration, storage, and provenance.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    @application.exception_handler(FitCheckError)
    async def fit_check_error_handler(_: Request, exc: FitCheckError) -> JSONResponse:
        status_code = {
            "OBJECT_NOT_FOUND": 404,
            "INVALID_OBJECT_KEY": 400,
            "DEMO_ENDPOINT_DISABLED": 404,
            "DEMO_SEED_CONFLICT": 409,
            "SMOKE_TEST_DISABLED": 403,
            "UPLOAD_NOT_FOUND": 404,
            "IMPORT_NOT_FOUND": 404,
            "CANDIDATE_NOT_FOUND": 404,
            "GARMENT_NOT_FOUND": 404,
            "UNSUPPORTED_UPLOAD_TYPE": 400,
            "UNSUPPORTED_IMAGE": 400,
            "INVALID_IMAGE": 400,
            "EMPTY_UPLOAD": 400,
            "UPLOAD_TOO_LARGE": 413,
            "UPLOAD_NOT_COMPLETE": 409,
            "UPLOAD_NOT_READY": 409,
            "REFERENCE_PHOTO_CONSENT_REQUIRED": 409,
            "MODEL_PROFILE_NOT_FOUND": 404,
            "MODEL_PROFILE_NOT_READY": 409,
            "LOCAL_PROFILE_UPLOAD_ENDPOINT_DISABLED": 404,
            "CANDIDATE_NOT_APPROVABLE": 409,
            "LOCAL_UPLOAD_ENDPOINT_DISABLED": 404,
            "GARMENT_NOT_CUTOUT_ELIGIBLE": 409,
            "CUTOUT_NOT_FOUND": 404,
            "CUTOUT_NOT_APPROVABLE": 409,
            "DUPLICATE_REVIEW_NOT_FOUND": 404,
            "INSUFFICIENT_APPROVED_GARMENTS": 409,
            "OUTFIT_NOT_FOUND": 404,
            "OUTFIT_EMPTY": 409,
            "OUTFIT_NOT_RENDERABLE": 409,
            "TRYON_PARENT_RUN_NOT_FOUND": 409,
            "TRYON_MODEL_NOT_CONFIGURED": 409,
            "TRYON_LIVE_INPUTS_UNVERIFIED": 409,
            "GENERATION_OUTPUT_UNVERIFIABLE": 502,
            "GENBLAZE_EXECUTION_FAILED": 502,
            "PROVIDER_GENERATION_FAILED": 502,
            "WEAR_EVENT_NOT_FOUND": 404,
        }.get(exc.code, 422)
        return JSONResponse(status_code=status_code, content=exc.as_dict())

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            app_env=settings.app_env,
            provider_mode=settings.provider_mode.value,
            storage_mode=settings.storage_mode.value,
            gmi_model_configured=bool(settings.gmi_image_model),
        )

    application.include_router(v1_router)
    return application


app = create_app()
