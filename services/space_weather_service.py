"""Safe NOAA SWPC JSON client. NOAA receives no operator/location information."""
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
 "kp":"https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
 "f107":"https://services.swpc.noaa.gov/json/f107_cm_flux.json",
 "alerts":"https://services.swpc.noaa.gov/products/alerts.json",
}
class SpaceWeatherError(RuntimeError): pass
class InternetConnectionError(SpaceWeatherError): pass


LOG = logging.getLogger(__name__)
_MAX_RESPONSE_BYTES = 1_000_000


def check_internet_connection(url: str, timeout_seconds: float = 4) -> None:
 """Check DNS and a TCP route before issuing NOAA requests.

 The probe is deliberately performed once per refresh, rather than retrying each
 NOAA endpoint when the device is offline.
 """
 parsed = urlparse(url)
 host = parsed.hostname
 if parsed.scheme != "https" or not host:
  raise InternetConnectionError("URL NOAA invalid pentru actualizarea propagării.")
 try:
  addresses = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
  LOG.debug("Propagare: DNS pentru %s a returnat %d adrese.", host, len(addresses))
 except socket.gaierror as exc:
  LOG.warning("Propagare: DNS nu poate rezolva %s: %s", host, exc)
  raise InternetConnectionError("Nu există conexiune la internet sau DNS nu funcționează.") from exc
 try:
  with socket.create_connection(addresses[0][4], timeout=timeout_seconds):
   LOG.debug("Propagare: conexiunea TCP către %s este disponibilă.", host)
 except OSError as exc:
  LOG.warning("Propagare: nu se poate conecta la %s: %s", host, exc)
  raise InternetConnectionError("Nu există conexiune la internet. Conectați dispozitivul la Wi-Fi și încercați din nou.") from exc

def _number(value: Any) -> float | None:
 try:
  value=float(value); return value if -10000 < value < 100000 else None
 except (TypeError, ValueError): return None
def _latest(rows: Any, fields: tuple[str,...]) -> float | None:
 if not isinstance(rows,list): return None
 for row in reversed(rows):
  if isinstance(row,dict):
   for field in fields:
    val=_number(row.get(field))
    if val is not None:return val
 return None
def _blackout(alerts: Any) -> str | None:
 text=json.dumps(alerts).upper()[:200000]
 for level in ("R5","R4","R3","R2","R1"):
  if "BLACKOUT" in text and level in text:return level
 return None
class SpaceWeatherService:
 def __init__(self, cache: PropagationCache | None=None, session: object | None=None) -> None:
  self.cache=cache or PropagationCache();self.session=session;self._internet_checked=False
 def _get(self,url:str) -> Any:
  if not self._internet_checked:
   LOG.debug("Propagare: se verifică accesul la internet înainte de cererea NOAA.")
   check_internet_connection(url)
   self._internet_checked=True
  last=None
  for attempt in range(2):
   try:
    LOG.debug("Propagare: cerere HTTP NOAA (%d/2): %s", attempt + 1, url)
    if self.session is not None:
     response=self.session.get(url,timeout=(6,20),headers={"Accept":"application/json"},stream=True)
     response.raise_for_status(); raw=response.raw.read(_MAX_RESPONSE_BYTES + 1)
    else:
     with urlopen(Request(url, headers={"Accept":"application/json", "User-Agent":"RadioLogbook/1.0"}), timeout=20) as response:
      LOG.debug("Propagare: răspuns HTTP NOAA %s pentru %s.", response.status, url)
      raw=response.read(_MAX_RESPONSE_BYTES + 1)
    if len(raw)>_MAX_RESPONSE_BYTES: raise SpaceWeatherError("Răspuns NOAA prea mare")
    text=raw.decode("utf-8")
    LOG.debug("Propagare: răspuns NOAA (%d octeți): %.500s", len(raw), text)
    return json.loads(text)
   except (HTTPError, URLError, OSError, UnicodeDecodeError, json.JSONDecodeError, SpaceWeatherError, AttributeError) as exc:
    last=exc
    LOG.warning("Propagare: cererea NOAA a eșuat (%s): %s", type(exc).__name__, exc)
    time.sleep(.2 * (attempt+1))
  raise SpaceWeatherError(f"NOAA indisponibil ({type(last).__name__}): {last}")
 def fetch(self, force: bool=False) -> SpaceWeatherData:
  LOG.debug("Propagare: inițializare actualizare NOAA (force=%s).", force)
  cached=None if force else self.cache.read_json(self.cache.weather_path(),900)
  if cached:
   LOG.debug("Propagare: se folosesc date NOAA valide din cache.")
   return self._from_dict(cached)
  self._internet_checked=False
  kp=self._get(NOAA_ENDPOINTS["kp"]); flux=self._get(NOAA_ENDPOINTS["f107"]); alerts=self._get(NOAA_ENDPOINTS["alerts"])
  now=datetime.now(timezone.utc); data={"kp_index":_latest(kp,("kp_index","kp")),"solar_flux":_latest(flux,("flux","f107","f10.7")),"a_index":_latest(kp,("a_running","a_index","a")),"sunspot_number":_latest(flux,("sunspot_number","sunspot")),"radio_blackout_level":_blackout(alerts),"source":"NOAA SWPC JSON","observed_at_utc":now.isoformat(),"fetched_at_utc":now.isoformat()}
  self.cache.write_json(self.cache.weather_path(),data)
  LOG.info("Propagare: datele NOAA au fost actualizate cu succes.")
  return self._from_dict(data)
 @staticmethod
 def _from_dict(data:dict)->SpaceWeatherData:
  observed=datetime.fromisoformat(data["observed_at_utc"]); fetched=datetime.fromisoformat(data["fetched_at_utc"])
  return SpaceWeatherData(**{k:data.get(k) for k in ("kp_index","a_index","solar_flux","sunspot_number","radio_blackout_level","source")}, observed_at_utc=observed,fetched_at_utc=fetched)
