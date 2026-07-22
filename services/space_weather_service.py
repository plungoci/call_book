"""NOAA SWPC client for the independent products used by the weather panel."""
from __future__ import annotations

import json
import logging
import socket
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from propagation_models import SpaceWeatherData
from .propagation_cache import PropagationCache

NOAA_ENDPOINTS = {
    "kp": "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
    "solar": "https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json",
    "xray": "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json",
    "proton": "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-3-day.json",
    "electron": "https://services.swpc.noaa.gov/json/goes/primary/integral-electrons-3-day.json",
    "plasma": "https://services.swpc.noaa.gov/json/rtsw/rtsw_plasma_1_hour.json",
    "magnetic": "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1_hour.json",
    "aurora": "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json",
    "alerts": "https://services.swpc.noaa.gov/products/alerts.json",
}
LOG = logging.getLogger(__name__)
_MAX_RESPONSE_BYTES = 1_000_000


class SpaceWeatherError(RuntimeError):
    pass


class InternetConnectionError(SpaceWeatherError):
    pass


def check_internet_connection(url: str, timeout_seconds: float = 4) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise InternetConnectionError("URL NOAA invalid pentru actualizarea propagării.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        with socket.create_connection(addresses[0][4], timeout=timeout_seconds):
            pass
    except (socket.gaierror, OSError) as exc:
        LOG.warning("[NOAA] Internet check failed for %s: %s", parsed.hostname, exc)
        raise InternetConnectionError("Nu există conexiune la internet.") from exc


def _number(value: Any, field: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        if value not in (None, "", "null"):
            LOG.warning("[NOAA] Field %s cannot be converted to a number: %r", field, value)
        return None
    if not -10_000 < number < 100_000:
        LOG.warning("[NOAA] Field %s has an implausible value: %r", field, value)
        return None
    return number


def _latest(rows: Any, fields: tuple[str, ...], label: str) -> float | None:
    if not isinstance(rows, list):
        LOG.warning("[NOAA] %s response is not a JSON array.", label)
        return None
    for row in reversed(rows):
        if isinstance(row, dict):
            for field in fields:
                if field in row:
                    value = _number(row[field], field)
                    if value is not None:
                        LOG.info("[NOAA] Field %s found.", label)
                        return value
    LOG.warning("[NOAA] Field %s missing.", label)
    return None


def _aurora_probability(payload: Any) -> float | None:
    coordinates = payload.get("coordinates") if isinstance(payload, dict) else None
    if not isinstance(coordinates, list):
        LOG.warning("[NOAA] Field AuroralActivity missing.")
        return None
    values = [_number(row.get("probability"), "probability") for row in coordinates if isinstance(row, dict)]
    values = [value for value in values if value is not None]
    if not values:
        LOG.warning("[NOAA] Field AuroralActivity contains no numeric probability.")
        return None
    LOG.info("[NOAA] Field AuroralActivity found.")
    return max(values)


def _blackout(alerts: Any) -> str | None:
    text = json.dumps(alerts).upper()[:200_000]
    return next((level for level in ("R5", "R4", "R3", "R2", "R1") if "BLACKOUT" in text and level in text), None)


class SpaceWeatherService:
    def __init__(self, cache: PropagationCache | None = None, session: object | None = None) -> None:
        self.cache = cache or PropagationCache()
        self.session = session
        self._internet_checked = False

    def _get(self, url: str) -> Any:
        if not self._internet_checked:
            check_internet_connection(url)
            self._internet_checked = True
        last: Exception | None = None
        for attempt in range(2):
            try:
                LOG.info("[NOAA] Download %s...", url.rsplit("/", 1)[-1])
                if self.session is not None:
                    response = self.session.get(url, timeout=(6, 20), headers={"Accept": "application/json"}, stream=True)
                    response.raise_for_status()
                    raw = response.raw.read(_MAX_RESPONSE_BYTES + 1)
                    LOG.info("[NOAA] Endpoint returned HTTP %s.", getattr(response, "status_code", 200))
                else:
                    with urlopen(Request(url, headers={"Accept": "application/json", "User-Agent": "RadioLogbook/1.0"}), timeout=20) as response:
                        raw = response.read(_MAX_RESPONSE_BYTES + 1)
                        LOG.info("[NOAA] Endpoint returned HTTP %s.", response.status)
                if len(raw) > _MAX_RESPONSE_BYTES:
                    raise SpaceWeatherError("Răspuns NOAA prea mare")
                LOG.info("[NOAA] Parsing JSON...")
                payload = json.loads(raw.decode("utf-8"))
                LOG.info("[NOAA] Parsed successfully.")
                return payload
            except (HTTPError, URLError, OSError, UnicodeDecodeError, json.JSONDecodeError, SpaceWeatherError, AttributeError) as exc:
                last = exc
                LOG.warning("[NOAA] Request failed (%s): %s", type(exc).__name__, exc)
                time.sleep(.2 * (attempt + 1))
        raise SpaceWeatherError(f"NOAA indisponibil ({type(last).__name__}): {last}")

    def fetch(self, force: bool = False) -> SpaceWeatherData:
        cached = None if force else self.cache.read_json(self.cache.weather_path(), 900)
        if cached:
            LOG.info("[NOAA] Using fresh cached data.")
            return self._from_dict(cached)
        self._internet_checked = False
        payloads = {name: self._get(url) for name, url in NOAA_ENDPOINTS.items()}
        now = datetime.now(timezone.utc)
        LOG.info("[NOAA] Parsing downloaded products.")
        data = {
            "kp_index": _latest(payloads["kp"], ("kp_index", "kp"), "K Index"),
            "a_index": _latest(payloads["kp"], ("a_running", "a_index", "a"), "A Index"),
            "solar_flux": _latest(payloads["solar"], ("f10.7", "f107", "flux"), "SFI"),
            "sunspot_number": _latest(payloads["solar"], ("ssn", "sunspot_number"), "SSN"),
            "xray_flux": _latest(payloads["xray"], ("observed_flux", "flux"), "XRayFlux"),
            "proton_flux": _latest(payloads["proton"], ("flux",), "ProtonFlux"),
            "electron_flux": _latest(payloads["electron"], ("flux",), "ElectronFlux"),
            "auroral_activity": _aurora_probability(payloads["aurora"]),
            "solar_wind_speed": _latest(payloads["plasma"], ("speed",), "SolarWindSpeed"),
            "solar_wind_density": _latest(payloads["plasma"], ("density",), "SolarWindDensity"),
            "bz": _latest(payloads["magnetic"], ("bz_gsm", "bz"), "Bz"),
            "radio_blackout_level": _blackout(payloads["alerts"]),
            "source": "NOAA SWPC JSON",
            "observed_at_utc": now.isoformat(),
            "fetched_at_utc": now.isoformat(),
        }
        self.cache.write_json(self.cache.weather_path(), data)
        return self._from_dict(data)

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> SpaceWeatherData:
        now = datetime.now(timezone.utc)
        observed = datetime.fromisoformat(data.get("observed_at_utc", now.isoformat()))
        fetched = datetime.fromisoformat(data.get("fetched_at_utc", now.isoformat()))
        names = ("kp_index", "a_index", "solar_flux", "sunspot_number", "radio_blackout_level", "source", "xray_flux", "proton_flux", "electron_flux", "auroral_activity", "solar_wind_speed", "solar_wind_density", "bz")
        return SpaceWeatherData(**{name: data.get(name) for name in names}, observed_at_utc=observed, fetched_at_utc=fetched)
