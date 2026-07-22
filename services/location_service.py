"""Privacy-preserving access to the locally configured Windows Location API."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import subprocess
import sys

class LocationError(RuntimeError): pass
class LocationUnavailableError(LocationError): pass
class LocationPermissionError(LocationError): pass
class LocationDisabledError(LocationError): pass
class LocationTimeoutError(LocationError): pass


LOG = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class LocationResult:
    latitude: float
    longitude: float
    accuracy_m: float | None
    source: str
    timestamp_utc: datetime

class LocationService:
    """Obtain a one-shot position from Windows Runtime; never uses network/IP."""
    timeout_seconds = 12
    _script = r'''Add-Type -AssemblyName System.Runtime.WindowsRuntime
$g = [Windows.Devices.Geolocation.Geolocator, Windows.Devices.Geolocation, ContentType=WindowsRuntime]::new()
$p = [System.WindowsRuntimeSystemExtensions]::AsTask($g.GetGeopositionAsync()).GetAwaiter().GetResult()
@{ latitude=$p.Coordinate.Point.Position.Latitude; longitude=$p.Coordinate.Point.Position.Longitude; accuracy=$p.Coordinate.Accuracy } | ConvertTo-Json -Compress'''
    def locate(self, timeout_seconds: int | None = None) -> LocationResult:
        if sys.platform != "win32":
            LOG.warning("Localizare: Windows Location nu este disponibil pe %s.", sys.platform)
            raise LocationUnavailableError("Platformă nesuportată")
        timeout = timeout_seconds or self.timeout_seconds
        LOG.debug("Localizare: inițializare Windows Location (timeout=%ss).", timeout)
        try:
            completed = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", self._script], capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            LOG.warning("Localizare: cererea către Windows Location a expirat după %ss.", timeout)
            raise LocationTimeoutError("Detectarea locației a expirat.") from exc
        output = completed.stdout.strip()
        if completed.returncode or not output:
            message = (completed.stderr or output).lower()
            LOG.warning("Localizare: Windows Location a eșuat (cod=%s): %s", completed.returncode, message[:500])
            if "access" in message or "denied" in message: raise LocationPermissionError("Permisiunea de localizare a fost refuzată.")
            if "disabled" in message or "location" in message and "service" in message: raise LocationDisabledError("Serviciul de localizare este dezactivat.")
            raise LocationUnavailableError("Locația nu a putut fi determinată.")
        LOG.debug("Localizare: răspuns Windows Location primit (%d octeți).", len(output))
        try:
            data = json.loads(output)
            latitude, longitude = float(data["latitude"]), float(data["longitude"])
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("coordonate în afara limitelor")
            accuracy = float(data["accuracy"]) if data.get("accuracy") is not None else None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            LOG.warning("Localizare: răspuns Windows Location invalid: %s", exc)
            raise LocationUnavailableError("Răspuns invalid de la Windows Location.") from exc
        LOG.info("Localizare: coordonate detectate cu succes (precizie disponibilă=%s).", accuracy is not None)
        return LocationResult(latitude, longitude, accuracy, "Windows Location", datetime.now(timezone.utc))
