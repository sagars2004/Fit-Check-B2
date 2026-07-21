from __future__ import annotations

from datetime import date

from httpx import ASGITransport, AsyncClient

from app.core.config import ProviderMode, Settings, StorageMode
from app.db.models import Garment, User
from app.main import create_app
from app.services.weather import WeatherSnapshot


class StaticColdRainWeather:
    async def forecast(self, location: str, forecast_date: date) -> WeatherSnapshot:
        return WeatherSnapshot(
            location=location,
            forecast_date=forecast_date,
            low_c=2.0,
            high_c=7.0,
            apparent_high_c=4.0,
            precipitation_probability=85,
            precipitation_mm=8.2,
            weather_code=63,
            wind_kph=26.0,
            condition="rainy",
            source="test",
        )


async def _seed_wardrobe(app, settings: Settings) -> None:  # type: ignore[no-untyped-def]
    garments = [
        ("Navy work shirt", "top", ["navy"], ["work", "smart"], 120),
        ("Cream knit", "sweater", ["cream"], ["winter", "warm"], 90),
        ("Green casual tee", "top", ["green"], ["casual"], 35),
        ("Black trousers", "trousers", ["black"], ["work"], 110),
        ("Blue jeans", "jeans", ["blue"], ["casual"], 80),
        ("Khaki shorts", "shorts", ["khaki"], ["summer"], 45),
        ("Navy rain jacket", "raincoat", ["navy"], ["rain", "winter"], 150),
        ("Black boots", "boots", ["black"], ["winter"], 140),
    ]
    async with app.state.database.session() as session:
        session.add(
            User(
                id=settings.demo_user_id,
                auth_subject="demo:local-owner",
                display_name="Fit Check local owner",
                default_location="New York, NY",
            )
        )
        for name, category, colors, tags, price in garments:
            session.add(
                Garment(
                    user_id=settings.demo_user_id,
                    name=name,
                    category=category,
                    colors=colors,
                    tags=tags,
                    seasons=[],
                    price=price,
                    status="approved",
                    evidence_status="verified_source_backed",
                )
            )
        session.add(
            Garment(
                user_id=settings.demo_user_id,
                name="Held rain shorts",
                category="shorts",
                colors=["black"],
                tags=[],
                seasons=[],
                status="needs_better_photo",
                evidence_status="needs_better_photo",
            )
        )
        await session.commit()


async def test_owned_only_cold_rain_recommendations_save_and_reversible_wear(tmp_path) -> None:
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
        app.state.weather = StaticColdRainWeather()
        await _seed_wardrobe(app, settings)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            recommendation = await client.post(
                "/v1/outfits/recommend",
                json={
                    "location": "New York, NY",
                    "forecast_date": "2026-01-10",
                    "occasion": "Rainy office commute",
                    "utilization_mode": True,
                },
            )
            assert recommendation.status_code == 201
            payload = recommendation.json()
            assert payload["weather"]["source"] == "test"
            assert len(payload["options"]) == 3

            primary_sets = []
            for option in payload["options"]:
                items = option["items"]
                assert any(item["role"] == "outerwear" for item in items)
                assert all(item["name"] != "Held rain shorts" for item in items)
                assert all(item["category"] != "shorts" for item in items)
                primary_sets.append(
                    frozenset(
                        item["garment_id"]
                        for item in items
                        if item["role"] in {"top", "bottom", "one_piece"}
                    )
                )
            assert len(set(primary_sets)) == 3

            outfit_id = payload["options"][0]["id"]
            saved = await client.post(f"/v1/outfits/{outfit_id}/save")
            assert saved.status_code == 200
            assert saved.json()["status"] == "saved"

            worn = await client.post(
                f"/v1/outfits/{outfit_id}/wear",
                json={"action": "wear", "worn_on": "2026-01-10", "notes": "Test commute."},
            )
            assert worn.status_code == 200
            assert worn.json()["outfit_status"] == "worn"
            assert set(worn.json()["garment_wear_counts"].values()) == {1}
            assert all(value is not None for value in worn.json()["garment_cost_per_wear"].values())

            undone = await client.post(
                f"/v1/outfits/{outfit_id}/wear",
                json={"action": "undo", "worn_on": "2026-01-10"},
            )
            assert undone.status_code == 200
            assert undone.json()["outfit_status"] == "saved"
            assert set(undone.json()["garment_wear_counts"].values()) == {0}
            assert set(undone.json()["garment_cost_per_wear"].values()) == {None}

            saved_looks = await client.get("/v1/outfits?status=saved")
            assert saved_looks.status_code == 200
            assert [look["id"] for look in saved_looks.json()] == [outfit_id]


async def test_recommendation_requires_owned_approved_outfit_components(tmp_path) -> None:
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
        app.state.weather = StaticColdRainWeather()
        async with app.state.database.session() as session:
            session.add(
                User(
                    id=settings.demo_user_id,
                    auth_subject="demo:local-owner",
                    display_name="Fit Check local owner",
                )
            )
            session.add(
                Garment(
                    user_id=settings.demo_user_id,
                    name="Held coat",
                    category="raincoat",
                    colors=["navy"],
                    tags=[],
                    seasons=[],
                    status="needs_better_photo",
                    evidence_status="needs_better_photo",
                )
            )
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/v1/outfits/recommend",
                json={"location": "New York, NY", "occasion": "Rainy commute"},
            )
            assert response.status_code == 409
            assert response.json()["code"] == "INSUFFICIENT_APPROVED_GARMENTS"
