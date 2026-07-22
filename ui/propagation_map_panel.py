"""Tk presentation only; network/map work is delegated to a worker thread."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk
from propagation_models import PropagationMapRequest
from services.propagation_map_service import PropagationMapService
from services.space_weather_service import InternetConnectionError, SpaceWeatherService
from .tooltip import Tooltip
class PropagationMapPanel(ttk.LabelFrame):
 def __init__(self,parent, profile_getter, on_expand=None):
  super().__init__(parent,text="Hartă propagare",padding=6);self.profile_getter=profile_getter;self.on_expand=on_expand;self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="propagation");self.request_id=0;self.after_id=None;self.closing=False;self.propagation_photo=None;self.internet_unavailable=False
  self.status=tk.StringVar(value="Selectează o bandă pentru afișarea estimării de propagare.");self.details=tk.StringVar(value="Estimare de propagare — fără date încărcate")
  top=ttk.Frame(self);top.pack(fill="x");ttk.Label(top,textvariable=self.status).pack(side="left");self.refresh_button=ttk.Button(top,text="Actualizează",command=lambda:self.schedule(self.band, self.frequency,0));self.refresh_button.pack(side="right");Tooltip(self.refresh_button,"Descarcă cele mai recente date disponibile și regenerează harta pentru banda selectată.")
  if on_expand: ttk.Button(top,text="Mărește",command=on_expand).pack(side="right",padx=4)
  self.image=ttk.Label(self,text="Selectează o bandă pentru afișarea estimării de propagare.",anchor="center");self.image.pack(fill="both",expand=True,pady=4);Tooltip(self.image,"Afișează o estimare a zonelor favorabile pentru banda selectată, folosind date actuale de vreme spațială.")
  ttk.Label(self,textvariable=self.details,wraplength=650,justify="left").pack(fill="x");ttk.Label(self,text="Legendă: Foarte slabă / Slabă / Moderată / Bună / Foarte bună. Modelele și contururile diferențiază zonele; estimare, nu garanție.",wraplength=650).pack(anchor="w")
  self.band="";self.frequency=None
 def schedule(self,band,frequency=None,delay=700):
  self.band=(band or "").strip();self.frequency=frequency
  if delay == 0:
   # A deliberate click is allowed to retry after the user restores Wi-Fi.
   self.internet_unavailable=False
  if self.after_id:
   try:self.after_cancel(self.after_id)
   except tk.TclError:pass
  if not self.band:self.status.set("Selectează o bandă pentru afișarea estimării de propagare.");return
  if self.internet_unavailable:
   self.status.set("Nu există conexiune la internet. Conectați dispozitivul la Wi-Fi, apoi apăsați Actualizează.")
   return
  self.request_id+=1; rid=self.request_id;self.after_id=self.after(delay,lambda:self._start(rid))
 def _start(self,rid):
  if self.closing or rid!=self.request_id:return
  profile=self.profile_getter()
  if profile.latitude is None or profile.longitude is None:self.status.set("Date indisponibile: completează coordonatele operatorului.");return
  self.status.set("Se descarcă datele…");self.refresh_button.config(state="disabled")
  request=PropagationMapRequest(profile.latitude,profile.longitude,profile.maidenhead_locator or profile.grid_square,self.band,self.frequency,None,profile.default_power_w,datetime.now(timezone.utc))
  future=self.executor.submit(self._work,request)
  future.add_done_callback(lambda f, request_id=rid:self.after(0,lambda: self._finish(request_id,f)))
 def _work(self,request):
  weather=SpaceWeatherService().fetch();return PropagationMapService().generate(request,weather),weather
 def _finish(self,rid,future):
  if self.closing or rid!=self.request_id:return
  self.refresh_button.config(state="normal")
  try:
   result,weather=future.result(); self.propagation_photo=tk.PhotoImage(file=result.image_path);self.image.config(image=self.propagation_photo,text="")
   def val(v):return "Indisponibil" if v is None else str(v)
   self.status.set("Date din cache" if result.is_cached else "Actualizat")
   self.details.set(f"Bandă: {result.band}; frecvență: {self.frequency or 'Indisponibil'} MHz; UTC: {result.generated_at_utc:%Y-%m-%d %H:%M}; sursă: {result.source_description}; SFI/F10.7: {val(weather.solar_flux)}; Kp: {val(weather.kp_index)}; A-index: {val(weather.a_index)}; pete: {val(weather.sunspot_number)}; blackout: {val(weather.radio_blackout_level)}. " + " ".join(result.warnings))
  except Exception as exc:
   if isinstance(exc, InternetConnectionError):
    self.internet_unavailable=True
    self.status.set("Nu există conexiune la internet. Conectați dispozitivul la Wi-Fi pentru actualizarea propagării.")
    self.details.set("Actualizarea automată este suspendată până apăsați Actualizează. Harta existentă este păstrată.")
   else:
    self.status.set("Actualizarea propagării a eșuat. Verifică legătura la internet și încearcă din nou.")
    self.details.set(f"Eroare de actualizare: {type(exc).__name__}: {exc}. Harta existentă este păstrată.")
 def shutdown(self):
  self.closing=True
  if self.after_id:
   try:self.after_cancel(self.after_id)
   except tk.TclError:pass
  self.executor.shutdown(wait=False,cancel_futures=True)
