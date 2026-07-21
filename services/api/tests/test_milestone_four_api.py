from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.core.config import ProviderMode, Settings, StorageMode
from app.main import create_app


def _settings(tmp_path) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(
        _env_file=None,
        app_env="test",
        provider_mode=ProviderMode.MOCK,
        storage_mode=StorageMode.LOCAL,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'runtime' / 'api.db'}",
        local_media_root=tmp_path / "media",
        public_media_base_url="http://testserver/v1/media",
    )


async def test_local_demo_seed_is_idempotent_and_makes_the_happy_path_reviewable(tmp_path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            first = await client.post("/v1/demo/seed")
            assert first.status_code == 200
            seeded = first.json()
            assert seeded["mode"] == "local_mock"
            assert seeded["created"] is True
            assert seeded["fixture_garment_count"] == 7
            assert seeded["approved_garment_count"] == 6
            assert seeded["profile_seeded"] is False
            assert "Synthetic local demo wardrobe" in seeded["disclosure"]

            second = await client.post("/v1/demo/seed")
            assert second.status_code == 200
            assert second.json()["created"] is False
            assert second.json()["fixture_garment_ids"] == seeded["fixture_garment_ids"]

            profiles = await client.get("/v1/model-profiles")
            assert profiles.status_code == 200
            assert profiles.json() == []

            garments = await client.get("/v1/garments")
            assert garments.status_code == 200
            garment_payloads = garments.json()
            assert {garment["id"] for garment in garment_payloads} == set(
                seeded["fixture_garment_ids"]
            )
            held_id = seeded["needs_better_photo_garment_id"]
            held = next(garment for garment in garment_payloads if garment["id"] == held_id)
            assert held["evidence_status"] == "needs_better_photo"

            source_backed = next(
                garment
                for garment in garment_payloads
                if garment["id"] in seeded["approved_garment_ids"]
            )
            assert source_backed["evidence_status"] == "verified_source_backed"
            assert source_backed["cutouts"][0]["qa_status"] == "approved"
            assert source_backed["cutouts"][0]["asset_url"]
            assert (await client.get(source_backed["cutouts"][0]["asset_url"])).status_code == 200

            provenance = await client.get(
                f"/v1/provenance/garment_asset/{source_backed['cutouts'][0]['id']}"
            )
            assert provenance.status_code == 200
            manifest = provenance.json()["manifest"]
            assert manifest["provider"] == "local"
            assert manifest["qa"]["synthetic_demo_fixture"] is True
            assert manifest["generation_parameters"]["source_is_personal_upload"] is False

            recommendation = await client.post(
                "/v1/outfits/recommend",
                json={
                    "location": "New York, NY",
                    "forecast_date": "2026-07-21",
                    "occasion": "Rainy workday",
                    "utilization_mode": True,
                },
            )
            assert recommendation.status_code == 201
            options = recommendation.json()["options"]
            assert len(options) == 3
            approved_ids = set(seeded["approved_garment_ids"])
            assert all(
                item["garment_id"] in approved_ids for option in options for item in option["items"]
            )
            assert all(
                item["garment_id"] != held_id for option in options for item in option["items"]
            )


async def test_demo_seed_is_disabled_outside_local_mock_mode(tmp_path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        # The storage instance was built for the isolated local test, but this
        # runtime setting proves the endpoint's own safety gate runs first.
        settings.storage_mode = StorageMode.B2
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            blocked = await client.post("/v1/demo/seed")
        assert blocked.status_code == 404
        assert blocked.json()["code"] == "DEMO_ENDPOINT_DISABLED"
