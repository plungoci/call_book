"""Resilient public space-weather clients and conservative aggregation.

Each provider is optional: NOAA SWPC supplies near-real-time solar-wind and
GOES products, SILSO supplies the official daily sunspot number, and GFZ
supplies Kp/Ap nowcast.  No credentials or personal data are sent.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import socket
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from propagation_models import SpaceWeatherData, WeatherValue
from .propagation_cache import PropagationCache

NOAA_ENDPOINTS = {
    "kp": "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json", "solar": "https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json",
    "xray": "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json", "proton": "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-3-day.json",
    "electron": "https://services.swpc.noaa.gov/json/goes/primary/integral-electrons-3-day.json", "plasma": "https://services.swpc.noaa.gov/json/rtsw/rtsw_plasma_1_hour.json",
    "magnetic": "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1_hour.json", "aurora": "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json", "alerts": "https://services.swpc.noaa.gov/products/alerts.json",
}
SILSO_ENDPOINT = "https://www.sidc.be/SILSO/INFO/sndtotcsv.php"
GFZ_ENDPOINT = "https://kp.gfz-potsdam.de/app/files/Kp_ap_nowcast.txt"
LOG = logging.getLogger(__name__); _MAX_RESPONSE_BYTES = 1_000_000

class SpaceWeatherError(RuntimeError): pass
class InternetConnectionError(SpaceWeatherError): pass

def check_internet_connection(url: str, timeout_seconds: float = 4) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname: raise InternetConnectionError("URL de date meteo spațiale invalid.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        with socket.create_connection(addresses[0][4], timeout=timeout_seconds): pass
    except (socket.gaierror, OSError) as exc: raise InternetConnectionError("Nu există conexiune la internet.") from exc

def _number(value: Any, field: str = "value") -> float | None:
    try: number = float(value)
    except (TypeError, ValueError): return None
    return number if -10_000 < number < 100_000 else None

def _latest(rows: Any, fields: tuple[str, ...]) -> float | None:
    if not isinstance(rows, list): return None
    for row in reversed(rows):
        if isinstance(row, dict):
            for field in fields:
                result = _number(row.get(field), field)
                if result is not None: return result
    return None

def _aurora_probability(payload: Any) -> float | None:
    rows = payload.get("coordinates", []) if isinstance(payload, dict) else []
    values = [_number(row.get("probability")) for row in rows if isinstance(row, dict)]
    return max((v for v in values if v is not None), default=None)

def _blackout(alerts: Any) -> str | None:
    text = json.dumps(alerts).upper()[:200_000]
    return next((level for level in ("R5", "R4", "R3", "R2", "R1") if "BLACKOUT" in text and level in text), None)

def parse_silso_daily_csv(payload: str) -> float | None:
    """Read the latest daily total sunspot number from SILSO semicolon CSV."""
    for row in reversed(list(csv.reader(io.StringIO(payload), delimiter=";"))):
        if len(row) >= 5 and row[0].strip()[:1].isdigit():
            value = _number(row[4])
            if value is not None and value >= 0: return value
    return None

def parse_gfz_nowcast(payload: str) -> tuple[float | None, float | None]:
    """Read final numeric Kp and ap columns from GFZ's whitespace nowcast text."""
    for line in reversed(payload.splitlines()):
        parts = line.split()
        if len(parts) >= 2 and parts[0][:4].isdigit():
            numbers = [_number(part) for part in parts]
            numbers = [n for n in numbers if n is not None]
            if len(numbers) >= 2: return numbers[-2], numbers[-1]
    return None, None

class SpaceWeatherService:
    def __init__(self, cache: PropagationCache | None = None, session: object | None = None) -> None:
        self.cache = cache or PropagationCache(); self.session = session; self._checked_hosts: set[str] = set()

    def _get(self, url: str, as_json: bool = True) -> Any:
        host = urlparse(url).hostname or ""
        if host not in self._checked_hosts: check_internet_connection(url); self._checked_hosts.add(host)
        last: Exception | None = None
        for attempt in range(2):
            try:
                if self.session is not None:
                    response = self.session.get(url, timeout=(6, 20), headers={"Accept": "application/json, text/plain"}, stream=True); response.raise_for_status(); raw = response.raw.read(_MAX_RESPONSE_BYTES + 1)
                else:
                    with urlopen(Request(url, headers={"Accept": "application/json, text/plain", "User-Agent": "RadioLogbook/1.0"}), timeout=20) as response: raw = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw) > _MAX_RESPONSE_BYTES: raise SpaceWeatherError("Răspuns prea mare")
                text = raw.decode("utf-8-sig")
                return json.loads(text) if as_json else text
            except HTTPError as exc:
                # 404 is not retried; 429 is retried once with backoff, never fatal to other providers.
                last = exc
                if exc.code == 404: break
            except (URLError, OSError, UnicodeDecodeError, json.JSONDecodeError, SpaceWeatherError, AttributeError) as exc: last = exc
            time.sleep(.2 * (attempt + 1))
        raise SpaceWeatherError(f"sursă indisponibilă ({type(last).__name__}): {last}")

    def _noaa(self) -> dict[str, float | str | None]:
        payloads: dict[str, Any] = {}
        for name, url in NOAA_ENDPOINTS.items():
            try: payloads[name] = self._get(url)
            except SpaceWeatherError as exc: LOG.warning("NOAA %s indisponibil: %s", name, exc)
        return {"kp_index": _latest(payloads.get("kp"), ("kp_index", "kp")), "a_index": _latest(payloads.get("kp"), ("a_running", "a_index", "a")), "solar_flux": _latest(payloads.get("solar"), ("f10.7", "f107", "flux")), "sunspot_number": _latest(payloads.get("solar"), ("ssn", "sunspot_number")), "xray_flux": _latest(payloads.get("xray"), ("observed_flux", "flux")), "proton_flux": _latest(payloads.get("proton"), ("flux",)), "electron_flux": _latest(payloads.get("electron"), ("flux",)), "auroral_activity": _aurora_probability(payloads.get("aurora")), "solar_wind_speed": _latest(payloads.get("plasma"), ("speed",)), "solar_wind_density": _latest(payloads.get("plasma"), ("density",)), "solar_wind_temperature": _latest(payloads.get("plasma"), ("temperature",)), "bz": _latest(payloads.get("magnetic"), ("bz_gsm", "bz")), "bt": _latest(payloads.get("magnetic"), ("bt", "bt_gsm")), "radio_blackout_level": _blackout(payloads.get("alerts", []))}

    def fetch(self, force: bool = False) -> SpaceWeatherData:
        cached = None if force else self.cache.read_json(self.cache.weather_path(), 900)
        if cached: return self._from_dict(cached)
        self._checked_hosts.clear(); now = datetime.now(timezone.utc); statuses: dict[str, str] = {}; noaa = self._noaa(); statuses["NOAA SWPC"] = "available" if any(v is not None for v in noaa.values()) else "unavailable"
        try: silso = parse_silso_daily_csv(self._get(SILSO_ENDPOINT, as_json=False)); statuses["SILSO"] = "available" if silso is not None else "no valid value"
        except Exception: silso = None; statuses["SILSO"] = "unavailable"
        try: gfz_kp, gfz_ap = parse_gfz_nowcast(self._get(GFZ_ENDPOINT, as_json=False)); statuses["GFZ Potsdam"] = "available" if gfz_kp is not None else "no valid value"
        except Exception: gfz_kp = gfz_ap = None; statuses["GFZ Potsdam"] = "unavailable"
        units = {"kp_index":"Kp", "a_index":"A", "ap_index":"Ap", "solar_flux":"sfu", "sunspot_number":"count", "xray_flux":"W/m²", "proton_flux":"pfu", "electron_flux":"particles/(cm²·s·sr)", "auroral_activity":"%", "solar_wind_speed":"km/s", "solar_wind_density":"p/cm³", "solar_wind_temperature":"K", "bz":"nT", "bt":"nT", "radio_blackout_level":"NOAA R"}
        selected = dict(noaa); sources = {key:"NOAA SWPC" for key, value in selected.items() if value is not None}
        if silso is not None: selected["sunspot_number"] = silso; sources["sunspot_number"] = "SIDC/SILSO"
        if gfz_kp is not None: selected["kp_index"] = gfz_kp; sources["kp_index"] = "GFZ Potsdam"
        if gfz_ap is not None: selected["ap_index"] = gfz_ap; sources["ap_index"] = "GFZ Potsdam"
        selected["dynamic_pressure"] = None
        if not any(value is not None for value in selected.values()):
            raise SpaceWeatherError("Niciun furnizor de date nu a răspuns cu valori valide.")
        values = {key: WeatherValue(value, units.get(key, ""), sources.get(key, "—"), now, "observed" if value is not None else "unavailable", "available" if value is not None else "unavailable") for key, value in selected.items()}
        data = {**selected, "source": ", ".join(name for name, status in statuses.items() if status == "available") or "Nicio sursă disponibilă", "observed_at_utc":now.isoformat(), "fetched_at_utc":now.isoformat(), "provider_status":statuses, "values": {k:{"value":v.value,"unit":v.unit,"source":v.source,"observed_at_utc":v.observed_at_utc.isoformat(),"quality":v.quality,"status":v.status} for k,v in values.items()}}
        self.cache.write_json(self.cache.weather_path(), data); return self._from_dict(data)

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> SpaceWeatherData:
        now = datetime.now(timezone.utc); observed = datetime.fromisoformat(data.get("observed_at_utc", now.isoformat())); fetched = datetime.fromisoformat(data.get("fetched_at_utc", now.isoformat()))
        values = {key: WeatherValue(item.get("value"), item.get("unit", ""), item.get("source", "—"), datetime.fromisoformat(item.get("observed_at_utc", observed.isoformat())), item.get("quality", "observed"), item.get("status", "available")) for key,item in data.get("values", {}).items() if isinstance(item, dict)}
        names = ("kp_index","a_index","solar_flux","sunspot_number","radio_blackout_level","source","xray_flux","proton_flux","electron_flux","auroral_activity","solar_wind_speed","solar_wind_density","bz","ap_index","bt","solar_wind_temperature","dynamic_pressure")
        return SpaceWeatherData(**{name:data.get(name) for name in names}, observed_at_utc=observed, fetched_at_utc=fetched, values=values or None, provider_status=data.get("provider_status"))
