"""One-shot, privacy-aware location providers used by the operator profile."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import math
import os
import socket
import ssl
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class LocationError(RuntimeError): pass
class LocationUnavailableError(LocationError): pass
class LocationPermissionError(LocationError): pass
class LocationDisabledError(LocationError): pass
class LocationTimeoutError(LocationError): pass
class LocationNetworkError(LocationError): pass
class LocationDnsError(LocationNetworkError): pass
class LocationInternetError(LocationNetworkError): pass
class LocationTlsError(LocationNetworkError): pass
class LocationHttpError(LocationNetworkError): pass
class LocationResponseError(LocationNetworkError): pass


LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LocationResult:
    latitude: float
    longitude: float
    accuracy_m: float | None
    source: str
    timestamp_utc: datetime


def _coordinates(data: dict) -> tuple[float, float, float | None]:
    """Read common provider field names and reject malformed coordinates."""
    latitude = data.get("latitude", data.get("lat"))
    longitude = data.get("longitude", data.get("lon", data.get("lng")))
    try:
        latitude, longitude = float(latitude), float(longitude)
        accuracy = data.get("accuracy", data.get("accuracy_m"))
        accuracy = None if accuracy is None else float(accuracy)
    except (TypeError, ValueError) as exc:
        raise LocationResponseError("Răspunsul nu conține coordonate numerice.") from exc
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise LocationResponseError("Răspunsul conține coordonate în afara limitelor.")
    if accuracy is not None and (not math.isfinite(accuracy) or accuracy < 0):
        raise LocationResponseError("Răspunsul conține o precizie invalidă.")
    return latitude, longitude, accuracy


class IpLocationService:
    """Configurable HTTPS IP-geolocation fallback with explicit network diagnostics."""
    endpoint = "https://ipwho.is/"
    timeout_seconds = 8

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint or os.environ.get("CALL_BOOK_LOCATION_ENDPOINT", self.endpoint)

    def locate(self, timeout_seconds: int | None = None) -> LocationResult:
        timeout = timeout_seconds or self.timeout_seconds
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            raise LocationResponseError("Endpointul de localizare trebuie să fie un URL HTTPS valid.")
        port = parsed.port or 443
        try:
            # DNS and TCP are deliberately checked separately so the UI can report the real cause.
            addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise LocationDnsError("Numele serviciului de localizare nu poate fi rezolvat (DNS).") from exc
        try:
            with socket.create_connection(addresses[0][4], timeout=timeout):
                pass
        except socket.timeout as exc:
            raise LocationTimeoutError("Conectarea la serviciul de localizare a expirat.") from exc
        except OSError as exc:
            raise LocationInternetError("Există rețea locală, dar serviciul de localizare nu poate fi atins.") from exc
        request = Request(self.endpoint, headers={"Accept": "application/json", "User-Agent": "CallBook/1.0"})
        try:
            with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
                status = response.status
                content_type = response.headers.get_content_type()
                body = response.read(64 * 1024)
        except HTTPError as exc:
            raise LocationHttpError(f"Serviciul de localizare a răspuns cu HTTP {exc.code}.") from exc
        except ssl.SSLCertVerificationError as exc:
            raise LocationTlsError("Certificatul TLS al serviciului de localizare nu este valid.") from exc
        except socket.timeout as exc:
            raise LocationTimeoutError("Cererea către serviciul de localizare a expirat.") from exc
        except URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                raise LocationTlsError("Conexiunea TLS la serviciul de localizare a eșuat.") from exc
            raise LocationInternetError("Cererea către serviciul de localizare a eșuat.") from exc
        if status < 200 or status >= 300:
            raise LocationHttpError(f"Serviciul de localizare a răspuns cu HTTP {status}.")
        if content_type not in {"application/json", "text/json"}:
            raise LocationResponseError(f"Serviciul a răspuns cu tipul de conținut neașteptat: {content_type}.")
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LocationResponseError("Serviciul de localizare a trimis JSON invalid.") from exc
        if not isinstance(data, dict) or data.get("success") is False:
            raise LocationResponseError("Serviciul de localizare nu a putut furniza coordonate.")
        latitude, longitude, accuracy = _coordinates(data)
        return LocationResult(latitude, longitude, accuracy, "Geolocalizare IP (ipwho.is)", datetime.now(timezone.utc))


class WindowsLocationService:
    """Obtain a one-shot position from Windows Runtime; never uses network/IP."""
    timeout_seconds = 12
    _script = r'''Add-Type -AssemblyName System.Runtime.WindowsRuntime
$g = [Windows.Devices.Geolocation.Geolocator, Windows.Devices.Geolocation, ContentType=WindowsRuntime]::new()
$operation = $g.GetGeopositionAsync()
$asTask = [System.WindowsRuntimeSystemExtensions]::AsTask($operation)
$p = $asTask.GetAwaiter().GetResult()
@{ latitude=$p.Coordinate.Point.Position.Latitude; longitude=$p.Coordinate.Point.Position.Longitude; accuracy=$p.Coordinate.Accuracy } | ConvertTo-Json -Compress'''
    def locate(self, timeout_seconds: int | None = None) -> LocationResult:
        timeout = timeout_seconds or self.timeout_seconds
        try:
            completed = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", self._script], capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise LocationTimeoutError("Detectarea locației Windows a expirat.") from exc
        output = completed.stdout.strip()
        if completed.returncode or not output:
            message = (completed.stderr or output).lower()
            if "access" in message or "denied" in message:
                raise LocationPermissionError("Permisiunea de localizare a fost refuzată.")
            if "disabled" in message or ("location" in message and "service" in message):
                raise LocationDisabledError("Serviciul de localizare este dezactivat.")
            raise LocationUnavailableError("Windows Location nu a putut furniza o poziție.")
        try:
            latitude, longitude, accuracy = _coordinates(json.loads(output))
        except (json.JSONDecodeError, TypeError) as exc:
            raise LocationUnavailableError("Răspuns invalid de la Windows Location.") from exc
        return LocationResult(latitude, longitude, accuracy, "Windows Location", datetime.now(timezone.utc))


class LocationService:
    """Prefer Windows sensors and fall back to configurable HTTPS IP geolocation."""
    def __init__(self, ip_service: IpLocationService | None = None) -> None:
        self.ip_service = ip_service or IpLocationService()

    def locate(self, timeout_seconds: int | None = None) -> LocationResult:
        if sys.platform == "win32":
            try:
                return WindowsLocationService().locate(timeout_seconds)
            except LocationError as exc:
                LOG.info("Windows Location indisponibilă; se încearcă fallback IP: %s", exc)
        return self.ip_service.locate(timeout_seconds)
