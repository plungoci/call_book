"""Simple terrestrial current-weather client for the station's own location.

Open-Meteo requires no API key and no credentials or personal data are sent
beyond the station's own latitude/longitude, already stored locally in the
operator profile.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests as curl_requests

_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
_SIBIU_METAR_ENDPOINT = "https://aviationweather.gov/api/data/metar"
_SIBIU_ICAO = "LRSB"
_DEFAULT_METAR_CACHE_PATH = Path("cache/local_weather/sibiu_metar.json")
# A routine METAR is only reissued roughly every 30-60 minutes, so re-fetching
# it on every weather refresh (which can be configured as often as every
# minute) gains nothing and risks the aviation-weather API rate-limiting or
# blocking the repeated requests — the same kind of bot-management NOAA SWPC
# applies to its own feeds (see space_weather_service). Reusing a recent
# fetch avoids hitting that in the first place.
_METAR_REFRESH_INTERVAL_SECONDS = 20 * 60
# If a fresh fetch fails, fall back to a not-too-stale cached reading instead
# of blanking out already-good data — the same "keep the last valid reading"
# principle the propagation panel uses. Matches the 3-hour window already
# requested from the API itself.
_METAR_FALLBACK_MAX_AGE_SECONDS = 3 * 60 * 60

LOG = logging.getLogger(__name__)

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
    atmospheric_pressure_hpa: float | None = None
    wind_speed_knots: float | None = None
    wind_direction_degrees: float | None = None

    @property
    def wind_speed_kmh(self) -> float | None:
        return self.wind_speed_knots * 1.852 if self.wind_speed_knots is not None else None


def _number(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class LocalWeatherService:
    """Fetch current temperature/humidity/conditions from Open-Meteo."""

    def __init__(self, metar_cache_path: Path | None = None) -> None:
        self.metar_cache_path = metar_cache_path or _DEFAULT_METAR_CACHE_PATH

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
        pressure, wind_speed, wind_direction = self._fetch_sibiu_airport_observation(timeout_seconds)
        return LocalWeatherData(
            temperature_c=_number(current.get("temperature_2m")),
            humidity_percent=_number(current.get("relative_humidity_2m")),
            condition=_CONDITIONS.get(int(code)) if code is not None else None,
            atmospheric_pressure_hpa=pressure,
            wind_speed_knots=wind_speed,
            wind_direction_degrees=wind_direction,
        )

    def _fetch_sibiu_airport_observation(
        self,
        timeout_seconds: float,
    ) -> tuple[float | None, float | None, float | None]:
        """Return pressure and wind from Sibiu Airport's latest METAR.

        Reuses a recent fetch instead of hitting the network every time (see
        _METAR_REFRESH_INTERVAL_SECONDS), and falls back to a still-reasonably
        fresh cached reading if a live fetch fails, instead of blanking out
        already-good data with N/A over a transient failure.
        """
        cached = self._read_metar_cache(_METAR_REFRESH_INTERVAL_SECONDS)
        if cached is not None:
            return cached
        try:
            response = curl_requests.get(
                _SIBIU_METAR_ENDPOINT,
                params={"ids": _SIBIU_ICAO, "format": "json", "taf": "false", "hours": "3"},
                timeout=timeout_seconds,
                impersonate="chrome",
            )
            response.raise_for_status()
            reports = json.loads(response.content.decode("utf-8"))
        except (curl_requests.errors.RequestsError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            LOG.warning("Observația METAR pentru aeroportul Sibiu nu este disponibilă: %s", exc)
            return self._read_metar_cache(_METAR_FALLBACK_MAX_AGE_SECONDS) or (None, None, None)

        if not isinstance(reports, list) or not reports or not isinstance(reports[0], dict):
            return self._read_metar_cache(_METAR_FALLBACK_MAX_AGE_SECONDS) or (None, None, None)
        report = reports[0]
        result = (_number(report.get("altim")), _number(report.get("wspd")), _number(report.get("wdir")))
        self._write_metar_cache(result)
        return result

    def _read_metar_cache(self, max_age_seconds: float) -> tuple[float | None, float | None, float | None] | None:
        try:
            data = json.loads(self.metar_cache_path.read_text(encoding="utf-8"))
            if time.time() - data["fetched_at"] <= max_age_seconds:
                return data["pressure"], data["wind_speed"], data["wind_direction"]
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
        return None

    def _write_metar_cache(self, result: tuple[float | None, float | None, float | None]) -> None:
        pressure, wind_speed, wind_direction = result
        try:
            self.metar_cache_path.parent.mkdir(parents=True, exist_ok=True)
            cached = {
                "fetched_at": time.time(),
                "pressure": pressure,
                "wind_speed": wind_speed,
                "wind_direction": wind_direction,
            }
            self.metar_cache_path.write_text(json.dumps(cached), encoding="utf-8")
        except OSError:
            LOG.warning("Cache-ul METAR pentru aeroportul Sibiu nu a putut fi scris.", exc_info=True)
