from __future__ import annotations

from io import BytesIO

from httpx import ASGITransport, AsyncClient
from PIL import Image, ImageDraw, PngImagePlugin
from sqlalchemy import func, select

from app.core.config import ProviderMode, Settings, StorageMode
from app.db.models import GarmentEvidence, Upload
from app.main import create_app
from app.services.image_processing import validate_cutout_png


def _photo_bytes(color: tuple[int, int, int] = (31, 63, 112)) -> bytes:
    image = Image.new("RGB", (120, 180), color)
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def _green_screen_garment_bytes(variant: str) -> bytes:
    """Different raw PNG bytes that normalize to the same source crop."""

    image = Image.new("RGB", (160, 220), (18, 188, 28))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [
            (58, 24),
            (102, 24),
            (124, 58),
            (110, 76),
            (104, 62),
            (104, 184),
            (56, 184),
            (56, 62),
            (50, 76),
            (36, 58),
        ],
        fill=(35, 89, 149),
    )
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("fit-check-test-variant", variant)
    output = BytesIO()
    image.save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


async def _create_approved_garment(
    client: AsyncClient, filename: str, content: bytes, content_type: str
) -> str:
    target = await client.post(
        "/v1/uploads/presign",
        json={"filename": filename, "content_type": content_type, "size_bytes": len(content)},
    )
    uploaded = await client.put(target.json()["upload_url"], content=content)
    created = await client.post("/v1/imports", json={"upload_ids": [uploaded.json()["upload_id"]]})
    candidate_id = created.json()["candidate_ids"][0]
    approved = await client.patch(f"/v1/candidates/{candidate_id}", json={"action": "approve"})
    assert approved.status_code == 200
    return str(approved.json()["garment_id"])


async def test_local_upload_import_review_and_closet_flow(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        provider_mode=ProviderMode.MOCK,
        storage_mode=StorageMode.LOCAL,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'runtime' / 'api.db'}",
        local_media_root=tmp_path / "media",
        public_media_base_url="http://testserver/v1/media",
    )
    app = create_app(settings)
    photo = _photo_bytes()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            presign = await client.post(
                "/v1/uploads/presign",
                json={
                    "filename": "navy-top.jpg",
                    "content_type": "image/jpeg",
                    "size_bytes": len(photo),
                },
            )
            assert presign.status_code == 201
            upload_target = presign.json()
            assert upload_target["mode"] == "api_proxy"
            assert "fit-check/users/" in upload_target["original_key"]
            assert "key_id" not in str(upload_target).lower()

            finalized = await client.put(upload_target["upload_url"], content=photo)
            assert finalized.status_code == 200
            finalized_payload = finalized.json()
            assert finalized_payload["status"] == "uploaded"
            assert finalized_payload["width"] == 120
            assert finalized_payload["height"] == 180
            assert finalized_payload["normalized_key"].endswith("/normalized.jpg")

            duplicate_target = await client.post(
                "/v1/uploads/presign",
                json={"filename": "copy.jpg", "content_type": "image/jpeg"},
            )
            duplicate = await client.put(duplicate_target.json()["upload_url"], content=photo)
            assert duplicate.status_code == 200
            assert duplicate.json()["duplicate"] is True
            assert duplicate.json()["upload_id"] == finalized_payload["upload_id"]

            imported = await client.post(
                "/v1/imports", json={"upload_ids": [finalized_payload["upload_id"]]}
            )
            assert imported.status_code == 201
            job = imported.json()
            assert job["status"] == "awaiting_review"
            assert job["candidate_count"] == 1
            assert job["stages"] == ["uploaded", "inventorying", "awaiting_review"]

            closet_before_approval = await client.get("/v1/garments")
            assert closet_before_approval.status_code == 200
            assert closet_before_approval.json() == []

            repeated_import = await client.post(
                "/v1/imports", json={"upload_ids": [finalized_payload["upload_id"]]}
            )
            assert repeated_import.status_code == 201
            assert repeated_import.json()["id"] == job["id"]

            candidates = await client.get("/v1/candidates")
            assert candidates.status_code == 200
            candidate = candidates.json()[0]
            assert candidate["status"] == "awaiting_review"
            assert candidate["attributes"]["category"] == "top"
            assert candidate["source_crop_key"]
            crop = await client.get(candidate["source_crop_url"])
            assert crop.status_code == 200
            assert crop.headers["content-type"] == "image/jpeg"

            edited = await client.patch(
                f"/v1/candidates/{candidate['id']}",
                json={
                    "action": "edit",
                    "name": "Navy work shirt",
                    "category": "top",
                    "colors": ["navy"],
                    "tags": ["work"],
                },
            )
            assert edited.status_code == 200
            assert edited.json()["attributes"]["name_suggestion"] == "Navy work shirt"

            approved = await client.patch(
                f"/v1/candidates/{candidate['id']}",
                json={"action": "approve", "notes": "Verified against the original photo."},
            )
            assert approved.status_code == 200
            approved_candidate = approved.json()
            assert approved_candidate["status"] == "approved"
            garment_id = approved_candidate["garment_id"]
            assert garment_id

            garments = await client.get("/v1/garments?category=top&color=navy")
            assert garments.status_code == 200
            garment = garments.json()[0]
            assert garment["id"] == garment_id
            assert garment["evidence_status"] == "verified_source_backed"
            source_key = garment["source_crop_key"]

            updated = await client.patch(
                f"/v1/garments/{garment_id}",
                json={"name": "Navy work overshirt", "tags": ["work", "layer"], "price": 129.5},
            )
            assert updated.status_code == 200
            assert updated.json()["name"] == "Navy work overshirt"
            assert updated.json()["source_crop_key"] == source_key
            assert updated.json()["price"] == 129.5

        async with app.state.database.session() as session:
            upload_count = await session.scalar(select(func.count()).select_from(Upload))
            evidence = await session.scalar(
                select(GarmentEvidence).where(GarmentEvidence.garment_id == garment_id)
            )
        assert upload_count == 1
        assert evidence is not None
        assert evidence.crop_key == source_key


async def test_invalid_local_upload_returns_a_safe_file_error(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        provider_mode=ProviderMode.MOCK,
        storage_mode=StorageMode.LOCAL,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'runtime' / 'api.db'}",
        local_media_root=tmp_path / "media",
        public_media_base_url="http://testserver/v1/media",
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            target = await client.post(
                "/v1/uploads/presign",
                json={"filename": "not-a-photo.jpg", "content_type": "image/jpeg"},
            )
            failed = await client.put(target.json()["upload_url"], content=b"not an image")
            assert failed.status_code == 400
            assert failed.json()["code"] == "INVALID_IMAGE"


async def test_hold_and_reject_keep_unapproved_candidates_out_of_the_closet(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        provider_mode=ProviderMode.MOCK,
        storage_mode=StorageMode.LOCAL,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'runtime' / 'api.db'}",
        local_media_root=tmp_path / "media",
        public_media_base_url="http://testserver/v1/media",
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:

            async def import_photo(filename: str, color: tuple[int, int, int]) -> str:
                photo = _photo_bytes(color)
                target = await client.post(
                    "/v1/uploads/presign",
                    json={"filename": filename, "content_type": "image/jpeg"},
                )
                uploaded = await client.put(target.json()["upload_url"], content=photo)
                created = await client.post(
                    "/v1/imports", json={"upload_ids": [uploaded.json()["upload_id"]]}
                )
                return created.json()["candidate_ids"][0]

            held_id = await import_photo("occluded.jpg", (160, 75, 70))
            held = await client.patch(f"/v1/candidates/{held_id}", json={"action": "hold"})
            assert held.status_code == 200
            assert held.json()["status"] == "needs_better_photo"
            assert "Capture the garment alone" in held.json()["unresolved_details"][-1]

            invalid_approval = await client.patch(
                f"/v1/candidates/{held_id}", json={"action": "approve"}
            )
            assert invalid_approval.status_code == 409
            assert invalid_approval.json()["code"] == "CANDIDATE_NOT_APPROVABLE"

            rejected_id = await import_photo("false-positive.jpg", (72, 126, 83))
            rejected = await client.patch(
                f"/v1/candidates/{rejected_id}", json={"action": "reject"}
            )
            assert rejected.status_code == 200
            assert rejected.json()["status"] == "rejected"

            closet = await client.get("/v1/garments")
            assert closet.status_code == 200
            assert closet.json() == []


async def test_source_derived_cutout_requires_qa_then_human_approval(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        provider_mode=ProviderMode.MOCK,
        storage_mode=StorageMode.LOCAL,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'runtime' / 'api.db'}",
        local_media_root=tmp_path / "media",
        public_media_base_url="http://testserver/v1/media",
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            garment_id = await _create_approved_garment(
                client, "green-screen-top.png", _green_screen_garment_bytes("first"), "image/png"
            )
            generated = await client.post(f"/v1/garments/{garment_id}/generate-cutout")
            assert generated.status_code == 200
            cutout = generated.json()
            assert cutout["qa_status"] == "awaiting_review"
            assert cutout["evidence_status"] == "verified_source_backed"
            rendered = await client.get(cutout["asset_url"])
            assert rendered.status_code == 200
            assert validate_cutout_png(rendered.content).passed

            before_review = await client.get("/v1/garments")
            assert before_review.json()[0]["canonical_asset_id"] is None
            assert before_review.json()[0]["cutouts"][0]["qa_status"] == "awaiting_review"

            approved = await client.patch(
                f"/v1/garments/{garment_id}/cutouts/{cutout['id']}/review",
                json={"action": "approve"},
            )
            assert approved.status_code == 200
            assert approved.json()["qa_status"] == "approved"

            garment = (await client.get("/v1/garments")).json()[0]
            assert garment["canonical_asset_id"] == cutout["id"]
            provenance = await client.get(f"/v1/provenance/garment_asset/{cutout['id']}")
            assert provenance.status_code == 200
            assert provenance.json()["manifest"]["qa"]["status"] == "awaiting_review"
            assert provenance.json()["manifest"]["source_object_keys"] == [
                garment["source_crop_key"]
            ]


async def test_opaque_source_is_held_instead_of_claimed_as_a_cutout(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        provider_mode=ProviderMode.MOCK,
        storage_mode=StorageMode.LOCAL,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'runtime' / 'api.db'}",
        local_media_root=tmp_path / "media",
        public_media_base_url="http://testserver/v1/media",
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            garment_id = await _create_approved_garment(
                client, "ordinary-photo.jpg", _photo_bytes(), "image/jpeg"
            )
            generated = await client.post(f"/v1/garments/{garment_id}/generate-cutout")
            assert generated.status_code == 200
            assert generated.json()["qa_status"] == "failed"
            assert "opaque_corners" in generated.json()["qa_warnings"]

            held = (await client.get("/v1/garments")).json()[0]
            assert held["status"] == "needs_better_photo"
            assert held["evidence_status"] == "needs_better_photo"
            assert held["canonical_asset_id"] is None


async def test_similar_cutouts_create_review_only_duplicate_suggestion(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        provider_mode=ProviderMode.MOCK,
        storage_mode=StorageMode.LOCAL,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'runtime' / 'api.db'}",
        local_media_root=tmp_path / "media",
        public_media_base_url="http://testserver/v1/media",
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            first_id = await _create_approved_garment(
                client, "first.png", _green_screen_garment_bytes("first"), "image/png"
            )
            first_asset = (await client.post(f"/v1/garments/{first_id}/generate-cutout")).json()
            first_review = await client.patch(
                f"/v1/garments/{first_id}/cutouts/{first_asset['id']}/review",
                json={"action": "approve"},
            )
            assert first_review.status_code == 200

            second_id = await _create_approved_garment(
                client, "second.png", _green_screen_garment_bytes("second"), "image/png"
            )
            second_asset = (await client.post(f"/v1/garments/{second_id}/generate-cutout")).json()
            second_review = await client.patch(
                f"/v1/garments/{second_id}/cutouts/{second_asset['id']}/review",
                json={"action": "approve"},
            )
            assert second_review.status_code == 200

            reviews = await client.get("/v1/duplicate-reviews")
            assert reviews.status_code == 200
            assert len(reviews.json()) == 1
            review = reviews.json()[0]
            assert review["status"] == "pending"
            assert review["score"] >= 0.96
            assert review["evidence"]["review_only"] is True
            assert {review["garment_a"]["id"], review["garment_b"]["id"]} == {
                first_id,
                second_id,
            }

            decision = await client.patch(
                f"/v1/duplicate-reviews/{review['id']}",
                json={"action": "keep_separate", "notes": "Different purchase dates."},
            )
            assert decision.status_code == 200
            assert decision.json()["status"] == "not_duplicate"
            assert decision.json()["reviewer_notes"] == "Different purchase dates."
            assert len((await client.get("/v1/garments")).json()) == 2
