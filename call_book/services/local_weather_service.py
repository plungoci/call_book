"""Simple terrestrial current-weather client for the station's own location.

Open-Meteo requires no API key and no credentials or personal data are sent
beyond the station's own latitude/longitude, already stored locally in the
operator profile.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from curl_cffi import requests as curl_requests

_ENDPOINT = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes, as returned by Open-Meteo's "weather_code".
_CONDITIONS = {
    0: "Cer senin",
    1: "Parțial senin",
    2: "Parțial noros",
    3: "Înnorat",
    45: "Ceață",
    48: "Ceață cu chiciură",
    51: "Burniță slabă",
    53: "Burniță moderată",
    55: "Burniță puternică",
    56: "Burniță înghețată slabă",
    57: "Burniță înghețată puternică",
    61: "Ploaie slabă",
    63: "Ploaie moderată",
    65: "Ploaie puternică",
    66: "Ploaie înghețată slabă",
    67: "Ploaie înghețată puternică",
    71: "Ninsoare slabă",
    73: "Ninsoare moderată",
    75: "Ninsoare puternică",
    77: "Grăunțe de zăpadă",
    80: "Aversă de ploaie slabă",
    81: "Aversă de ploaie moderată",
    82: "Aversă de ploaie puternică",
    85: "Aversă de ninsoare slabă",
    86: "Aversă de ninsoare puternică",
    95: "Furtună",
    96: "Furtună cu grindină slabă",
    99: "Furtună cu grindină puternică",
}


class LocalWeatherError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LocalWeatherData:
    temperature_c: float | None
    humidity_percent: float | None
    condition: str | None


def _number(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class LocalWeatherService:
    """Fetch current temperature/humidity/conditions from Open-Meteo."""

    def fetch(self, latitude: float, longitude: float, timeout_seconds: float = 10) -> LocalWeatherData:
        params = {
            "latitude": f"{latitude:.4f}",
            "longitude": f"{longitude:.4f}",
            "current": "temperature_2m,relative_humidity_2m,weather_code",
            "timezone": "auto",
        }
        try:
            response = curl_requests.get(_ENDPOINT, params=params, timeout=timeout_seconds, impersonate="chrome")
            response.raise_for_status()
            data = json.loads(response.content.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LocalWeatherError(f"Vremea locală indisponibilă: {exc}") from exc
        current = data.get("current") if isinstance(data, dict) else None
        if not isinstance(current, dict):
            raise LocalWeatherError("Răspunsul nu conține date meteo curente.")
        code = _number(current.get("weather_code"))
        return LocalWeatherData(
            temperature_c=_number(current.get("temperature_2m")),
            humidity_percent=_number(current.get("relative_humidity_2m")),
            condition=_CONDITIONS.get(int(code)) if code is not None else None,
        )
