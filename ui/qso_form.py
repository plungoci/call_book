from __future__ import annotations
import tkinter as tk
from datetime import datetime, timezone
from tkinter import ttk
from models import QSO
from validators import band_for_frequency
from .tooltip import Tooltip
MODES=("FM","AM","SSB","USB","LSB","CW","RTTY","FT8","FT4","PSK31","DIGITAL"); QSL=("NOT_SENT","SENT","RECEIVED","CONFIRMED")
class QSOForm(ttk.LabelFrame):
 def __init__(self,parent,repeaters,on_save):
  super().__init__(parent,text="QSO (toate orele sunt UTC)",padding=8);self.repeaters=repeaters;self.on_save=on_save;self.qso_id=None;self.vars={k:tk.StringVar() for k in ("callsign","operator_name","repeater","frequency_mhz","band","mode","rst_sent","rst_received","grid_square","power_w","qsl_status","qso_start_utc","qso_end_utc")};self._build();self.new()
 def _build(self):
  descriptions={
   "callsign":"Indicativul stației cu care ai realizat legătura.\nExemplu: YO8ABC",
   "operator_name":"Numele operatorului, dacă este cunoscut.",
   "repeater":self._repeater_tooltip,
   "frequency_mhz":self._frequency_tooltip,
   "band":"Se completează automat după frecvență, dar poate fi modificată.",
   "mode":"Modul de lucru utilizat:\nFM, SSB, CW, FT8 etc.",
   "rst_sent":"Raportul transmis către corespondent.\nExemplu: 59 sau 599.",
   "rst_received":"Raportul primit de la corespondent.",
   "grid_square":"Locator Maidenhead al corespondentului.\nExemplu: KN27OD",
   "power_w":"Puterea de emisie în wați.\nExemplu: 5 W sau 50 W.",
   "qsl_status":"Starea confirmării QSL pentru această legătură.",
   "qso_start_utc":"Data și ora de început a QSO-ului, în UTC.",
   "qso_end_utc":"Data și ora de sfârșit a QSO-ului, în UTC.",
  }
  labels=[("Indicativ","callsign"),("Nume","operator_name"),("Repetor","repeater"),("Frecvență MHz","frequency_mhz"),("Bandă","band"),("Mod","mode"),("RST trimis","rst_sent"),("RST primit","rst_received"),("Locator","grid_square"),("Putere W","power_w"),("QSL","qsl_status"),("Început UTC","qso_start_utc"),("Sfârșit UTC","qso_end_utc")]
  for i,(label,key) in enumerate(labels):
   ttk.Label(self,text=label).grid(row=i//2*2,column=i%2*2,sticky="w",padx=3)
   widget=ttk.Combobox(self,textvariable=self.vars[key],state="readonly" if key in ("repeater","mode","qsl_status") else "normal",width=28) if key in ("repeater","mode","qsl_status") else ttk.Entry(self,textvariable=self.vars[key],width=30)
   if key=="mode":widget["values"]=MODES
   elif key=="qsl_status":widget["values"]=QSL
   elif key=="repeater":widget["values"]=["" ]+[f"{r['id']} — {r['name']}" for r in self.repeaters()];widget.bind("<<ComboboxSelected>>",self._repeater)
   widget.grid(row=i//2*2+1,column=i%2*2,sticky="ew",padx=3);setattr(self,key+"_widget",widget);Tooltip(widget,descriptions[key])
  ttk.Label(self,text="Observații").grid(row=14,column=0,sticky="w");self.notes=tk.Text(self,width=65,height=3);self.notes.grid(row=15,column=0,columnspan=4,sticky="ew",padx=3);Tooltip(self.notes,"Informații suplimentare despre QSO.")
 def _frequency_tooltip(self):
  frequency=self.vars["frequency_mhz"].get().strip()
  band=self.vars["band"].get().strip()
  text=f"Frecvența utilizată pentru QSO, exprimată în MHz.\nExemplu: 145.500"
  if frequency:text=f"Frecvență: {frequency} MHz\nBandă detectată: {band or 'necunoscută'}"
  return text
 def _repeater_tooltip(self):
  selected=self.vars["repeater"].get().split(" ")[0]
  repeater=next((r for r in self.repeaters() if str(r["id"]) == selected),None)
  if not repeater:return "Selectează repetorul utilizat.\nCompletarea automată va seta frecvența și modul."
  details=[str(repeater["name"]),f"{repeater['output_frequency_mhz']} MHz"]
  if repeater["shift_mhz"] is not None:details.append(f"Shift {repeater['shift_mhz'] * 1000:g} kHz")
  if repeater["tone_hz"] is not None:details.append(f"CTCSS {repeater['tone_hz']:g} Hz")
  return "\n".join(details)
 def _repeater(self,_):
  text=self.vars["repeater"].get()
  if not text:return
  r=next(r for r in self.repeaters() if str(r["id"])==text.split(" ")[0]);self.vars["frequency_mhz"].set(r["output_frequency_mhz"]);self.vars["mode"].set(r["mode"] or "FM");self.vars["band"].set(band_for_frequency(r["output_frequency_mhz"]))
 def new(self):
  self.qso_id=None
  for var in self.vars.values():var.set("")
  self.vars["qso_start_utc"].set(datetime.now(timezone.utc).replace(microsecond=0).isoformat());self.vars["mode"].set("FM");self.vars["qsl_status"].set("NOT_SENT");self.notes.delete("1.0","end");self.callsign_widget.focus_set()
 def load(self,q:QSO):
  self.qso_id=q.id
  for key in self.vars:
   if hasattr(q,key):self.vars[key].set(str(getattr(q,key) or ""))
  self.vars["repeater"].set(f"{q.repeater_id} —" if q.repeater_id else "");self.notes.delete("1.0","end");self.notes.insert("1.0",q.notes)
 def value(self)->QSO:
  v=self.vars; rep=v["repeater"].get().split(" ")[0];return QSO(id=self.qso_id,callsign=v["callsign"].get(),operator_name=v["operator_name"].get(),repeater_id=int(rep) if rep.isdigit() else None,frequency_mhz=float(v["frequency_mhz"].get()),band=v["band"].get(),mode=v["mode"].get(),rst_sent=v["rst_sent"].get(),rst_received=v["rst_received"].get(),grid_square=v["grid_square"].get(),power_w=float(v["power_w"].get()) if v["power_w"].get() else None,qsl_status=v["qsl_status"].get(),qso_start_utc=v["qso_start_utc"].get(),qso_end_utc=v["qso_end_utc"].get(),notes=self.notes.get("1.0","end-1c"))
