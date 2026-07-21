from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Any, Protocol

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class WeatherSnapshot:
    location: str
    forecast_date: date
    low_c: float
    high_c: float
    apparent_high_c: float
    precipitation_probability: int
    precipitation_mm: float
    weather_code: int
    wind_kph: float
    condition: str
    source: str
    advisory: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "forecast_date": self.forecast_date.isoformat(),
            "low_c": self.low_c,
            "high_c": self.high_c,
            "apparent_high_c": self.apparent_high_c,
            "precipitation_probability": self.precipitation_probability,
            "precipitation_mm": self.precipitation_mm,
            "weather_code": self.weather_code,
            "wind_kph": self.wind_kph,
            "condition": self.condition,
            "source": self.source,
            "advisory": self.advisory,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> WeatherSnapshot:
        return cls(
            location=str(value["location"]),
            forecast_date=date.fromisoformat(str(value["forecast_date"])),
            low_c=float(value["low_c"]),
            high_c=float(value["high_c"]),
            apparent_high_c=float(value.get("apparent_high_c", value["high_c"])),
            precipitation_probability=int(value["precipitation_probability"]),
            precipitation_mm=float(value["precipitation_mm"]),
            weather_code=int(value["weather_code"]),
            wind_kph=float(value["wind_kph"]),
            condition=str(value["condition"]),
            source=str(value["source"]),
            advisory=_optional_string(value.get("advisory")),
        )


class WeatherClient(Protocol):
    async def forecast(self, location: str, forecast_date: date) -> WeatherSnapshot: ...


class WeatherService:
    """Keyless Open-Meteo weather with an offline deterministic demo fallback."""

    _GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    _FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def forecast(self, location: str, forecast_date: date) -> WeatherSnapshot:
        normalized_location = location.strip()
        if self.settings.weather_mode == "mock":
            return _mock_snapshot(normalized_location, forecast_date)
        try:
            return await self._open_meteo_snapshot(normalized_location, forecast_date)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError):
            fallback = _mock_snapshot(normalized_location, forecast_date)
            return WeatherSnapshot(
                location=fallback.location,
                forecast_date=fallback.forecast_date,
                low_c=fallback.low_c,
                high_c=fallback.high_c,
                apparent_high_c=fallback.apparent_high_c,
                precipitation_probability=fallback.precipitation_probability,
                precipitation_mm=fallback.precipitation_mm,
                weather_code=fallback.weather_code,
                wind_kph=fallback.wind_kph,
                condition=fallback.condition,
                source="mock_fallback",
                advisory=(
                    "Live weather was unavailable, so Fit Check used a deterministic demo "
                    "forecast. Confirm conditions before leaving."
                ),
            )

    async def _open_meteo_snapshot(self, location: str, forecast_date: date) -> WeatherSnapshot:
        timeout = httpx.Timeout(self.settings.weather_request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            geocoded = await client.get(
                self._GEOCODING_URL,
                params={"name": location, "count": 1, "language": "en", "format": "json"},
            )
            geocoded.raise_for_status()
            result = geocoded.json()["results"][0]
            forecast = await client.get(
                self._FORECAST_URL,
                params={
                    "latitude": result["latitude"],
                    "longitude": result["longitude"],
                    "timezone": "auto",
                    "start_date": forecast_date.isoformat(),
                    "end_date": forecast_date.isoformat(),
                    "daily": ",".join(
                        [
                            "temperature_2m_max",
                            "temperature_2m_min",
                            "apparent_temperature_max",
                            "precipitation_probability_max",
                            "precipitation_sum",
                            "weather_code",
                            "wind_speed_10m_max",
                        ]
                    ),
                },
            )
            forecast.raise_for_status()
            daily = forecast.json()["daily"]

        resolved_location = ", ".join(
            part
            for part in [result.get("name"), result.get("admin1"), result.get("country")]
            if part
        )
        code = int(daily["weather_code"][0])
        return WeatherSnapshot(
            location=resolved_location or location,
            forecast_date=forecast_date,
            low_c=round(float(daily["temperature_2m_min"][0]), 1),
            high_c=round(float(daily["temperature_2m_max"][0]), 1),
            apparent_high_c=round(float(daily["apparent_temperature_max"][0]), 1),
            precipitation_probability=int(daily["precipitation_probability_max"][0] or 0),
            precipitation_mm=round(float(daily["precipitation_sum"][0] or 0), 1),
            weather_code=code,
            wind_kph=round(float(daily["wind_speed_10m_max"][0] or 0), 1),
            condition=_condition_for_code(code),
            source="open_meteo",
        )


def _mock_snapshot(location: str, forecast_date: date) -> WeatherSnapshot:
    """Generate a stable local forecast that keeps demos offline and repeatable."""

    digest = sha256(f"{location.casefold()}|{forecast_date.isoformat()}".encode()).digest()
    low_c = float(4 + digest[0] % 14)
    high_c = low_c + float(5 + digest[1] % 8)
    precipitation_probability = [10, 20, 35, 55, 70][digest[2] % 5]
    precipitation_mm = (
        0.0 if precipitation_probability < 35 else round(0.8 + (digest[3] % 19) / 5, 1)
    )
    weather_code = (
        3 if precipitation_probability < 35 else (61 if precipitation_probability < 60 else 63)
    )
    return WeatherSnapshot(
        location=location,
        forecast_date=forecast_date,
        low_c=low_c,
        high_c=high_c,
        apparent_high_c=round(high_c - (digest[4] % 4) * 0.7, 1),
        precipitation_probability=precipitation_probability,
        precipitation_mm=precipitation_mm,
        weather_code=weather_code,
        wind_kph=float(8 + digest[5] % 25),
        condition=_condition_for_code(weather_code),
        source="mock",
        advisory="Deterministic local demo forecast — switch WEATHER_MODE=live for Open-Meteo.",
    )


def _condition_for_code(code: int) -> str:
    if code in {0, 1}:
        return "clear"
    if code in {2, 3}:
        return "cloudy"
    if code in {45, 48}:
        return "foggy"
    if 51 <= code <= 67:
        return "rainy"
    if 71 <= code <= 77:
        return "snowy"
    if 80 <= code <= 82:
        return "showery"
    if 95 <= code <= 99:
        return "stormy"
    return "variable"


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None
