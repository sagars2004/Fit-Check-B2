from httpx import ASGITransport, AsyncClient

from app.core.config import ProviderMode, Settings, StorageMode
from app.main import create_app


async def test_health_and_mock_provenance_routes(tmp_path) -> None:
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
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.json()["provider_mode"] == "mock"

            created = await client.post(
                "/v1/demo/mock-cutout", json={"garment_name": "Test jacket"}
            )
            assert created.status_code == 201
            asset = created.json()

            provenance = await client.get(f"/v1/provenance/garment_asset/{asset['asset_id']}")
            assert provenance.status_code == 200
            assert provenance.json()["manifest"]["output"]["sha256"] == asset["sha256"]

            media = await client.get(f"/v1/media/{asset['object_key']}")
            assert media.status_code == 200
            assert media.headers["content-type"] == "image/png"
