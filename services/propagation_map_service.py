"""Local, simplified propagation estimates; deliberately not a VOACAP prediction."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import struct, zlib
from propagation_models import BandCondition, PropagationMapRequest, PropagationMapResult, SpaceWeatherData
from .propagation_cache import PropagationCache
HF={"160m","80m","60m","40m","30m","20m","17m","15m","12m","10m"}; VHF={"4m","2m","1.25m","70cm","33cm","23cm"}
def _norm(b:str)->str:return "".join((b or "").lower().replace(",",".").split())
def evaluate_band_conditions(band,space_weather,timestamp_utc,latitude,longitude):
 """Heuristic: SFI helps high HF; Kp/A/blackouts penalize HF. Never a guarantee."""
 del latitude,longitude;b=_norm(band);s=50.;w=[]
 if b in HF:
  if space_weather.solar_flux is None:w.append("SFI indisponibil; estimare redusă")
  else:s+=(space_weather.solar_flux-100)*(.45 if b in {"20m","17m","15m","12m","10m"} else .18)
  s-=max(0,(space_weather.kp_index or 2)-2)*9;s-=max(0,(space_weather.a_index or 8)-8)*.7
  if space_weather.radio_blackout_level:s-=25;w.append(f"Blackout radio {space_weather.radio_blackout_level}")
  if b in {"80m","40m","160m"} and 6<=timestamp_utc.hour<=18:s-=14
 elif b=="6m":s=35;w.append("Deschiderile Sporadic-E nu pot fi confirmate numai din indicii solari disponibili.")
 else:s=55;w.append("Rază line-of-sight orientativă; nu este predicție ionosferică.")
 s=max(0,min(100,s));rating="Foarte slabă" if s<20 else "Slabă" if s<40 else "Moderată" if s<60 else "Bună" if s<80 else "Foarte bună";return BandCondition(rating,s,f"Estimare simplificată: {rating.lower()} ({s:.0f}/100).",tuple(w))
def _png(path,w,h,pixels):
 raw=b''.join(b'\0'+bytes(row) for row in pixels);chunk=lambda typ,data:struct.pack('>I',len(data))+typ+data+struct.pack('>I',zlib.crc32(typ+data)&0xffffffff)
 path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,9))+chunk(b'IEND',b''))
class PropagationMapService:
 algorithm_version="local-heuristic-v1"
 def __init__(self,cache=None):self.cache=cache or PropagationCache()
 def generate(self,request,weather):
  if not(-90<=request.latitude<=90 and -180<=request.longitude<=180):raise ValueError("Coordonatele operatorului sunt invalide.")
  key=self.cache.key({"v":self.algorithm_version,"band":_norm(request.band),"freq":request.frequency_mhz,"lat":round(request.latitude,1),"lon":round(request.longitude,1),"hour":request.prediction_time_utc.strftime("%Y%m%d%H")});png,meta=self.cache.map_paths(key)
  if png.exists() and meta.exists() and datetime.now(timezone.utc).timestamp()-png.stat().st_mtime<900:return PropagationMapResult(str(png),request.band,datetime.fromtimestamp(png.stat().st_mtime,timezone.utc),weather.observed_at_utc,"NOAA SWPC JSON + estimare locală","redusă",True,())
  c=evaluate_band_conditions(request.band,weather,request.prediction_time_utc,request.latitude,request.longitude);self._render(png,request,c);meta.write_text("{}",encoding="utf-8");self.cache.prune();return PropagationMapResult(str(png),request.band,datetime.now(timezone.utc),weather.observed_at_utc,"NOAA SWPC JSON + estimare locală (nu VOACAP)","redusă",False,c.warnings)
 def _render(self,path,r,c):
  # Dependency-free PNG: patterned concentric zones and operator marker; UI carries text alternative/legend.
  w,h=960,460;cx,cy=w//2,h//2;palette=[(205,205,205),(231,189,82),(99,168,91),(24,118,184),(101,65,154)];pixels=[]
  for y in range(h):
   row=[]
   for x in range(w):
    d=((x-cx)**2+(y-cy)**2)**.5;idx=min(4,int(d/(min(w,h)/10)));color=palette[idx]
    if int(d)%38<2:color=(30,30,30)
    if abs(x-cx)<3 or abs(y-cy)<3:color=(40,40,40)
    if (x-cx)**2+(y-cy)**2<70:color=(220,35,35)
    row.extend(color)
   pixels.append(row)
  _png(path,w,h,pixels)
