"""Safe NOAA SWPC JSON client. NOAA receives no operator/location information."""
from __future__ import annotations
import json, time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from propagation_models import SpaceWeatherData
from .propagation_cache import PropagationCache

NOAA_ENDPOINTS = {
 "kp":"https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
 "f107":"https://services.swpc.noaa.gov/json/f107_cm_flux.json",
 "predicted_f107":"https://services.swpc.noaa.gov/json/predicted_f107_cm_flux.json",
 "alerts":"https://services.swpc.noaa.gov/products/alerts.json",
 "a_index":"https://services.swpc.noaa.gov/json/wing_kp_1m.json",
}
class SpaceWeatherError(RuntimeError): pass

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
  self.cache=cache or PropagationCache();self.session=session
 def _get(self,url:str) -> Any:
  last=None
  for attempt in range(2):
   try:
    if self.session is not None:
     response=self.session.get(url,timeout=(4,10),headers={"Accept":"application/json"},stream=True); response.raise_for_status(); raw=response.raw.read(1_000_001)
    else:
     with urlopen(Request(url, headers={"Accept":"application/json"}), timeout=14) as response: raw=response.read(1_000_001)
    if len(raw)>1_000_000: raise SpaceWeatherError("Răspuns NOAA prea mare")
    return json.loads(raw.decode("utf-8"))
   except (HTTPError, URLError, OSError, UnicodeDecodeError, json.JSONDecodeError, SpaceWeatherError, AttributeError) as exc:
    last=exc; time.sleep(.2 * (attempt+1))
  raise SpaceWeatherError(f"NOAA indisponibil: {type(last).__name__}")
 def fetch(self, force: bool=False) -> SpaceWeatherData:
  cached=None if force else self.cache.read_json(self.cache.weather_path(),900)
  if cached:return self._from_dict(cached)
  kp=self._get(NOAA_ENDPOINTS["kp"]); flux=self._get(NOAA_ENDPOINTS["f107"]); ai=self._get(NOAA_ENDPOINTS["a_index"]); alerts=self._get(NOAA_ENDPOINTS["alerts"])
  now=datetime.now(timezone.utc); data={"kp_index":_latest(kp,("kp_index","kp")),"solar_flux":_latest(flux,("flux","f107","f10.7")),"a_index":_latest(ai,("a_index","a")),"sunspot_number":_latest(flux,("sunspot_number","sunspot")),"radio_blackout_level":_blackout(alerts),"source":"NOAA SWPC JSON","observed_at_utc":now.isoformat(),"fetched_at_utc":now.isoformat()}
  self.cache.write_json(self.cache.weather_path(),data);return self._from_dict(data)
 @staticmethod
 def _from_dict(data:dict)->SpaceWeatherData:
  observed=datetime.fromisoformat(data["observed_at_utc"]); fetched=datetime.fromisoformat(data["fetched_at_utc"])
  return SpaceWeatherData(**{k:data.get(k) for k in ("kp_index","a_index","solar_flux","sunspot_number","radio_blackout_level","source")}, observed_at_utc=observed,fetched_at_utc=fetched)
