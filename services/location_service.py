"""Privacy-preserving access to the locally configured Windows Location API."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json, subprocess, sys

class LocationError(RuntimeError): pass
class LocationUnavailableError(LocationError): pass
class LocationPermissionError(LocationError): pass
class LocationDisabledError(LocationError): pass
class LocationTimeoutError(LocationError): pass

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
            raise LocationUnavailableError("Platformă nesuportată")
        try:
            completed = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", self._script], capture_output=True, text=True, timeout=timeout_seconds or self.timeout_seconds, check=False)
        except subprocess.TimeoutExpired as exc:
            raise LocationTimeoutError("Detectarea locației a expirat.") from exc
        output = completed.stdout.strip()
        if completed.returncode or not output:
            message = (completed.stderr or output).lower()
            if "access" in message or "denied" in message: raise LocationPermissionError("Permisiunea de localizare a fost refuzată.")
            if "disabled" in message or "location" in message and "service" in message: raise LocationDisabledError("Serviciul de localizare este dezactivat.")
            raise LocationUnavailableError("Locația nu a putut fi determinată.")
        try: data = json.loads(output)
        except json.JSONDecodeError as exc: raise LocationUnavailableError("Răspuns invalid de la Windows Location.") from exc
        return LocationResult(float(data["latitude"]), float(data["longitude"]), float(data["accuracy"]) if data.get("accuracy") is not None else None, "Windows Location", datetime.now(timezone.utc))
