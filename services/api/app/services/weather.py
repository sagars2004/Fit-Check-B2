from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class WeatherSnapshot:
    location: str
    forecast_date: date
    low_f: float
    high_f: float
    apparent_high_f: float
    precipitation_probability: int
    precipitation_inch: float
    weather_code: int
    wind_mph: float
    condition: str
    source: str
    advisory: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "forecast_date": self.forecast_date.isoformat(),
            "low_f": self.low_f,
            "high_f": self.high_f,
            "apparent_high_f": self.apparent_high_f,
            "precipitation_probability": self.precipitation_probability,
            "precipitation_inch": self.precipitation_inch,
            "weather_code": self.weather_code,
            "wind_mph": self.wind_mph,
            "condition": self.condition,
            "source": self.source,
            "advisory": self.advisory,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> WeatherSnapshot:
        apparent_val = value.get("apparent_high_f")
        if apparent_val is None:
            apparent_val = value["high_f"]

        return cls(
            location=str(value["location"]),
            forecast_date=date.fromisoformat(str(value["forecast_date"])),
            low_f=float(value["low_f"]),
            high_f=float(value["high_f"]),
            apparent_high_f=float(apparent_val),
            precipitation_probability=int(value["precipitation_probability"]),
            precipitation_inch=float(value["precipitation_inch"]),
            weather_code=int(value["weather_code"]),
            wind_mph=float(value["wind_mph"]),
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
                low_f=fallback.low_f,
                high_f=fallback.high_f,
                apparent_high_f=fallback.apparent_high_f,
                precipitation_probability=fallback.precipitation_probability,
                precipitation_inch=fallback.precipitation_inch,
                weather_code=fallback.weather_code,
                wind_mph=fallback.wind_mph,
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
                    "temperature_unit": "fahrenheit",
                    "wind_speed_unit": "mph",
                    "precipitation_unit": "inch",
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
            low_f=round(float(daily["temperature_2m_min"][0]), 1),
            high_f=round(float(daily["temperature_2m_max"][0]), 1),
            apparent_high_f=round(float(daily["apparent_temperature_max"][0]), 1),
            precipitation_probability=int(daily["precipitation_probability_max"][0] or 0),
            precipitation_inch=round(float(daily["precipitation_sum"][0] or 0), 2),
            weather_code=code,
            wind_mph=round(float(daily["wind_speed_10m_max"][0] or 0), 1),
            condition=_condition_for_code(code),
            source="open_meteo",
        )


def _mock_snapshot(location: str, forecast_date: date) -> WeatherSnapshot:
    """Generate a stable local forecast that keeps demos offline and repeatable."""

    return WeatherSnapshot(
        location=location or "Seattle, WA",
        forecast_date=forecast_date,
        low_f=45.5,
        high_f=58.0,
        apparent_high_f=55.2,
        precipitation_probability=80,
        precipitation_inch=0.3,
        weather_code=61,
        wind_mph=12.5,
        condition="Rain",
        source="mock_deterministic",
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
