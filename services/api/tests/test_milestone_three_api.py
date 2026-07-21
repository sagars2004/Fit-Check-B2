from __future__ import annotations

from io import BytesIO

from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import func, select

from app.core.config import ProviderMode, Settings, StorageMode
from app.core.errors import FitCheckError
from app.db.models import (
    Garment,
    GarmentEvidence,
    OutfitItem,
    OutfitPlan,
    TryOnRender,
    User,
    new_id,
)
from app.domain.enums import GarmentStatus, OutfitStatus
from app.main import create_app
from app.providers.mock import MockMediaOrchestrator
from app.services.object_keys import ObjectKeys


def _photo_bytes(color: tuple[int, int, int] = (68, 93, 144)) -> bytes:
    image = Image.new("RGB", (144, 216), color)
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        provider_mode=ProviderMode.MOCK,
        storage_mode=StorageMode.LOCAL,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'runtime' / 'api.db'}",
        local_media_root=tmp_path / "media",
        public_media_base_url="http://testserver/v1/media",
    )


async def _seed_renderable_outfit(app, settings: Settings) -> tuple[str, list[str]]:
    user_id = settings.demo_user_id
    outfit_id = new_id()
    garment_ids = [new_id(), new_id()]
    evidence_ids = [new_id(), new_id()]
    keys = ObjectKeys(settings.b2_prefix)
    source_keys = [
        keys.garment_source_crop(user_id, garment_id, evidence_id)
        for garment_id, evidence_id in zip(garment_ids, evidence_ids, strict=True)
    ]
    for source_key, color in zip(source_keys, [(35, 67, 122), (66, 74, 88)], strict=True):
        await app.state.storage.put_bytes(
            source_key,
            _photo_bytes(color),
            content_type="image/jpeg",
            metadata={"role": "source-crop"},
        )

    async with app.state.database.session() as session:
        session.add(
            User(
                id=user_id,
                auth_subject="demo:milestone-three",
                display_name="Fit Check local owner",
                default_location="New York, NY",
            )
        )
        garments = [
            Garment(
                id=garment_ids[0],
                user_id=user_id,
                name="Navy review top",
                category="top",
                colors=["navy"],
                tags=["work"],
                seasons=["spring"],
                status=GarmentStatus.APPROVED.value,
                evidence_status="verified_source_backed",
            ),
            Garment(
                id=garment_ids[1],
                user_id=user_id,
                name="Charcoal review trousers",
                category="trousers",
                colors=["gray"],
                tags=["work"],
                seasons=["spring"],
                status=GarmentStatus.APPROVED.value,
                evidence_status="verified_source_backed",
            ),
        ]
        outfit = OutfitPlan(
            id=outfit_id,
            user_id=user_id,
            weather_snapshot={"condition": "clear", "high_c": 20, "low_c": 12},
            occasion="Office review",
            score=0.9,
            reasoning="A source-backed owned look for an office review.",
            status=OutfitStatus.SAVED.value,
            planner_run_id="local-outfit-planner-source-run",
        )
        session.add_all([*garments, outfit])
        for garment_id, evidence_id, source_key in zip(
            garment_ids, evidence_ids, source_keys, strict=True
        ):
            session.add(
                GarmentEvidence(
                    id=evidence_id,
                    garment_id=garment_id,
                    crop_key=source_key,
                    role="primary",
                    notes="Immutable source crop for virtual preview testing.",
                )
            )
        session.add_all(
            [
                OutfitItem(id=new_id(), outfit_id=outfit_id, garment_id=garment_ids[0], role="top"),
                OutfitItem(
                    id=new_id(), outfit_id=outfit_id, garment_id=garment_ids[1], role="bottom"
                ),
            ]
        )
        await session.commit()
    return outfit_id, garment_ids


async def _create_active_profile(client: AsyncClient) -> dict[str, object]:
    photo = _photo_bytes((124, 96, 74))
    requested = await client.post(
        "/v1/model-profiles/presign",
        json={
            "filename": "reference.jpg",
            "content_type": "image/jpeg",
            "size_bytes": len(photo),
            "consent": True,
        },
    )
    assert requested.status_code == 201
    uploaded = await client.put(requested.json()["upload_url"], content=photo)
    assert uploaded.status_code == 200
    return dict(uploaded.json())


async def test_reference_photo_requires_consent_finalizes_and_deletes_independently(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            blocked = await client.post(
                "/v1/model-profiles/presign",
                json={"filename": "reference.jpg", "content_type": "image/jpeg", "consent": False},
            )
            assert blocked.status_code == 409
            assert blocked.json()["code"] == "REFERENCE_PHOTO_CONSENT_REQUIRED"

            active = await _create_active_profile(client)
            assert active["status"] == "active"
            assert active["sha256"]
            assert active["source_image_url"]
            profile_id = str(active["id"])

            idempotent_finalize = await client.post(f"/v1/model-profiles/{profile_id}/finalize")
            assert idempotent_finalize.status_code == 200
            assert idempotent_finalize.json()["id"] == profile_id

            profiles = await client.get("/v1/model-profiles")
            assert profiles.status_code == 200
            assert [profile["id"] for profile in profiles.json()] == [profile_id]

            original_media = await client.get(str(active["source_image_url"]))
            assert original_media.status_code == 200
            assert original_media.headers["content-type"] == "image/jpeg"

            deleted = await client.delete(f"/v1/model-profiles/{profile_id}")
            assert deleted.status_code == 204
            assert (await client.get("/v1/model-profiles")).json() == []
            assert (await client.get(str(active["source_image_url"]))).status_code == 404


async def test_mock_tryon_persists_source_lineage_and_retry_parent(tmp_path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        outfit_id, garment_ids = await _seed_renderable_outfit(app, settings)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            profile = await _create_active_profile(client)
            first = await client.post(
                f"/v1/outfits/{outfit_id}/render",
                json={"profile_id": profile["id"]},
            )
            assert first.status_code == 201
            first_payload = first.json()
            assert first_payload["status"] == "preview_ready"
            assert first_payload["provider"] == "mock"
            assert first_payload["model"] == "fit-check-local-mock-v1"
            assert first_payload["parent_run_id"] == "local-outfit-planner-source-run"
            assert set(first_payload["source_garment_ids"]) == set(garment_ids)
            assert len(first_payload["source_garments"]) == 2
            assert all(source["image_url"] for source in first_payload["source_garments"])
            assert {source["source_kind"] for source in first_payload["source_garments"]} == {
                "source_crop_fallback"
            }
            assert "AI preview" in first_payload["disclosure"]
            preview_media = await client.get(first_payload["render_url"])
            assert preview_media.status_code == 200
            assert preview_media.headers["content-type"] == "image/png"

            provenance = await client.get(f"/v1/provenance/tryon_render/{first_payload['id']}")
            assert provenance.status_code == 200
            manifest = provenance.json()["manifest"]
            assert manifest["pipeline_slug"] == "fit-check-m3-tryon-preview"
            assert manifest["qa"]["evidence_status"] == "ai_reconstructed"
            assert manifest["output"]["object_key"] == first_payload["object_key"]
            assert manifest["source_asset_ids"][0] == profile["id"]
            assert set(manifest["generation_parameters"]["selected_garment_ids"]) == set(
                garment_ids
            )
            assert "http://" not in str(manifest)
            assert "https://" not in str(manifest)

            retry = await client.post(
                f"/v1/outfits/{outfit_id}/render",
                json={
                    "profile_id": profile["id"],
                    "parent_run_id": first_payload["run_id"],
                    "correction_hint": "Use a neutral studio background.",
                },
            )
            assert retry.status_code == 201
            assert retry.json()["parent_run_id"] == first_payload["run_id"]
            assert retry.json()["run_id"] != first_payload["run_id"]

            renders = await client.get(f"/v1/outfits/{outfit_id}/renders")
            assert renders.status_code == 200
            assert [render["id"] for render in renders.json()] == [
                retry.json()["id"],
                first_payload["id"],
            ]


async def test_render_refuses_unapproved_outfit_items(tmp_path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        outfit_id, garment_ids = await _seed_renderable_outfit(app, settings)
        async with app.state.database.session() as session:
            garment = await session.scalar(select(Garment).where(Garment.id == garment_ids[1]))
            assert garment is not None
            garment.status = GarmentStatus.NEEDS_BETTER_PHOTO.value
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            profile = await _create_active_profile(client)
            rejected = await client.post(
                f"/v1/outfits/{outfit_id}/render",
                json={"profile_id": profile["id"]},
            )
            assert rejected.status_code == 409
            assert rejected.json()["code"] == "OUTFIT_NOT_RENDERABLE"
            assert (await client.get(f"/v1/outfits/{outfit_id}/renders")).json() == []


class _FailingOrchestrator:
    async def generate_image(self, _request) -> object:
        raise FitCheckError(
            "PROVIDER_GENERATION_FAILED",
            "The test provider did not create a preview.",
            retryable=True,
            correlation_id="provider-test-run",
        )


class _NeverCalledOrchestrator:
    async def generate_image(self, _request) -> object:
        raise AssertionError("Live preview gating must happen before provider orchestration.")


async def test_failed_preview_persists_retry_lineage_without_losing_the_outfit(tmp_path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        outfit_id, _ = await _seed_renderable_outfit(app, settings)
        app.state.orchestrator = _FailingOrchestrator()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            profile = await _create_active_profile(client)
            failed = await client.post(
                f"/v1/outfits/{outfit_id}/render",
                json={"profile_id": profile["id"]},
            )
            assert failed.status_code == 502
            assert failed.json()["code"] == "PROVIDER_GENERATION_FAILED"

            failed_renders = await client.get(f"/v1/outfits/{outfit_id}/renders")
            assert failed_renders.status_code == 200
            failed_render = failed_renders.json()[0]
            assert failed_render["status"] == "failed"
            assert failed_render["error_code"] == "PROVIDER_GENERATION_FAILED"
            assert failed_render["parent_run_id"] == "local-outfit-planner-source-run"
            assert failed_render["run_id"].startswith("tryon-failed-")

            failed_manifest = await client.get(f"/v1/provenance/tryon_render/{failed_render['id']}")
            assert failed_manifest.status_code == 200
            assert failed_manifest.json()["manifest"]["status"] == "failed"
            assert failed_manifest.json()["manifest"]["qa"]["retryable"] is True

            app.state.orchestrator = MockMediaOrchestrator()
            retry = await client.post(
                f"/v1/outfits/{outfit_id}/render",
                json={
                    "profile_id": profile["id"],
                    "parent_run_id": failed_render["run_id"],
                },
            )
            assert retry.status_code == 201
            assert retry.json()["parent_run_id"] == failed_render["run_id"]

        async with app.state.database.session() as session:
            outfit = await session.scalar(select(OutfitPlan).where(OutfitPlan.id == outfit_id))
            render_count = await session.scalar(
                select(func.count())
                .select_from(TryOnRender)
                .where(TryOnRender.outfit_id == outfit_id)
            )
        assert outfit is not None
        assert outfit.status == OutfitStatus.PREVIEW_READY.value
        assert render_count == 2


async def test_live_tryon_is_gated_before_reference_urls_can_reach_a_provider(tmp_path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        outfit_id, _ = await _seed_renderable_outfit(app, settings)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            profile = await _create_active_profile(client)
            # The app was intentionally booted in safe mock mode. Flipping this
            # runtime value lets the test prove that no live provider call is
            # attempted until an operator sets a capability-tested model ID.
            settings.provider_mode = ProviderMode.LIVE
            gated = await client.post(
                f"/v1/outfits/{outfit_id}/render",
                json={"profile_id": profile["id"]},
            )
            assert gated.status_code == 409
            assert gated.json()["code"] == "TRYON_MODEL_NOT_CONFIGURED"

            renders = await client.get(f"/v1/outfits/{outfit_id}/renders")
            assert renders.status_code == 200
            assert renders.json()[0]["status"] == "failed"
            assert renders.json()[0]["provider"] == "gmicloud"

            settings.gmi_tryon_model = "configured-after-capability-test"
            app.state.orchestrator = _NeverCalledOrchestrator()
            input_gated = await client.post(
                f"/v1/outfits/{outfit_id}/render",
                json={"profile_id": profile["id"]},
            )
            assert input_gated.status_code == 409
            assert input_gated.json()["code"] == "TRYON_LIVE_INPUTS_UNVERIFIED"
