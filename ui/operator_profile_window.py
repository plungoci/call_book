"""Dialog used to maintain the logbook owner's personal data and local location."""
from __future__ import annotations
import threading
import tkinter as tk
from datetime import datetime, timezone
from tkinter import messagebox, ttk
from database import Database
from models import OperatorProfile
from services.location_service import (LocationDisabledError, LocationDnsError, LocationHttpError,
    LocationInternetError, LocationPermissionError, LocationResponseError, LocationService,
    LocationTimeoutError, LocationTlsError, LocationUnavailableError)
from utils.maidenhead import coordinates_to_maidenhead
from validators import normalize_callsign, normalize_name
from .tooltip import Tooltip
from .common_widgets import ScrollableFrame

class OperatorProfileWindow(tk.Toplevel):
    FIELDS = (("Indicativ personal", "callsign"), ("Nume complet", "full_name"),
        ("Latitudine", "latitude"), ("Longitudine", "longitude"),
        ("Precizie localizare (m)", "location_accuracy_m"), ("Sursa localizării", "location_source"),
        ("Locator Maidenhead", "grid_square"), ("Localitate", "locality"), ("Județ", "county"),
        ("Țară", "country"), ("Adresă", "address"), ("Email", "email"), ("Telefon", "phone"),
        ("Echipament radio", "radio_equipment"), ("Antenă", "antenna"),
        ("Putere implicită (W)", "default_power_w"), ("Club radio", "radio_club"), ("Indicativ club", "club_callsign"))
    LOCATION_TIPS = {"latitude":"Coordonata nord-sud, între -90 și 90 de grade.\nPoate fi completată automat sau manual.", "longitude":"Coordonata est-vest, între -180 și 180 de grade.\nPoate fi completată automat sau manual.", "location_accuracy_m":"Precizia estimată a localizării, exprimată în metri.\nO valoare mai mică indică o localizare mai precisă.", "grid_square":"Locator radio calculat pe baza coordonatelor geografice.\nExemplu: KN34BK."}
    def __init__(self, parent: tk.Misc, db: Database) -> None:
        super().__init__(parent); self.db=db; self.title("Date operator"); self.geometry("610x680"); self.minsize(460, 420); self.transient(parent)
        self.vars={name:tk.StringVar() for _,name in self.FIELDS}; self.detect_button=None; self._build(); self.load_profile(); self.grab_set()
    def _build(self) -> None:
        scrollable = ScrollableFrame(self)
        scrollable.pack(fill="both", expand=True)
        content=ttk.Frame(scrollable.content,padding=12); content.pack(fill="both",expand=True)
        content.columnconfigure(1, weight=1)
        for i,(label,name) in enumerate(self.FIELDS):
            ttk.Label(content,text=label).grid(row=i,column=0,sticky="w",pady=2)
            entry=ttk.Entry(content,textvariable=self.vars[name],width=42); entry.grid(row=i,column=1,sticky="ew",pady=2)
            if name in self.LOCATION_TIPS: Tooltip(entry,self.LOCATION_TIPS[name])
        row=len(self.FIELDS)
        actions=ttk.Frame(content); actions.grid(row=row,column=0,columnspan=2,pady=(5,2))
        self.detect_button=ttk.Button(actions,text="Detectează locația",command=self.detect_location); self.detect_button.pack(side="left",padx=3)
        Tooltip(self.detect_button,"Folosește Windows Location când este disponibil; altfel, cu acordul declanșat de acest buton, estimează poziția după adresa IP.")
        recalc=ttk.Button(actions,text="Recalculează locatorul",command=self.recalculate_locator); recalc.pack(side="left",padx=3)
        Tooltip(recalc,"Calculează locatorul Maidenhead folosind latitudinea și longitudinea introduse.")
        ttk.Label(content,text="Locația este utilizată local pentru calcularea locatorului Maidenhead.",foreground="#555555").grid(row=row+1,column=0,columnspan=2,sticky="w",pady=(2,4))
        ttk.Label(content,text="Observații").grid(row=row+2,column=0,sticky="nw",pady=2); self.notes=tk.Text(content,width=40,height=4); self.notes.grid(row=row+2,column=1,sticky="ew",pady=2)
        buttons=ttk.Frame(content); buttons.grid(row=row+3,column=0,columnspan=2,pady=(8,0))
        for text,command in (("Salvează",self.save),("Resetează",self.reset),("Închide",self.destroy)): ttk.Button(buttons,text=text,command=command).pack(side="left",padx=3)
    def load_profile(self) -> None:
        profile=self.db.get_operator_profile()
        for name,var in self.vars.items():
            value=getattr(profile,name)
            if name == "grid_square" and not value: value=profile.maidenhead_locator
            var.set("" if value is None else str(value))
        self.notes.delete("1.0","end"); self.notes.insert("1.0",profile.notes)
    def recalculate_locator(self) -> None:
        try:
            grid=coordinates_to_maidenhead(float(self.vars["latitude"].get()),float(self.vars["longitude"].get())).upper()
        except ValueError as exc: messagebox.showerror("Eroare",f"Coordonate invalide: {exc}",parent=self); return
        self.vars["grid_square"].set(grid)
    def detect_location(self) -> None:
        self.detect_button.config(state="disabled",text="Se detectează locația…"); self.config(cursor="watch")
        threading.Thread(target=self._detect_worker,daemon=True).start()
    def _detect_worker(self) -> None:
        try: result=LocationService().locate()
        except Exception as exc: self.after(0,lambda error=exc:self._location_error(error)); return
        self.after(0,lambda location=result:self._apply_location(location))
    def _finish_detection(self) -> None:
        self.detect_button.config(state="normal",text="Detectează locația"); self.config(cursor="")
    def _apply_location(self,result) -> None:
        self._finish_detection(); detected=coordinates_to_maidenhead(result.latitude,result.longitude).upper(); old=self.vars["grid_square"].get().strip().upper()
        if old and old != detected:
            choice=messagebox.askyesnocancel("Locator detectat",f"Locatorul salvat este: {old}\nLocatorul detectat este: {detected}\n\nDorești să înlocuiești locatorul existent?\n\nDa = Înlocuiește; Nu = Păstrează valoarea existentă; Anulare = nu actualiza formularul.",parent=self)
            if choice is None:return
        self.vars["latitude"].set(f"{result.latitude:.6f}"); self.vars["longitude"].set(f"{result.longitude:.6f}"); self.vars["location_accuracy_m"].set("" if result.accuracy_m is None else f"{result.accuracy_m:.1f}"); self.vars["location_source"].set(result.source)
        self._detected_at=result.timestamp_utc.isoformat()
        if not old or old == detected or choice: self.vars["grid_square"].set(detected)
    def _location_error(self, exc: Exception) -> None:
        self._finish_detection()
        if isinstance(exc,LocationDisabledError): text="Serviciul de localizare Windows este dezactivat.\n\nActivează:\nSetări Windows → Confidențialitate și securitate → Locație\n\nApoi încearcă din nou."
        elif isinstance(exc,LocationPermissionError): text="Permisiunea pentru localizare este refuzată. Permite accesul aplicațiilor la locație în setările Windows."
        elif isinstance(exc,LocationTimeoutError): text="Detectarea locației a durat prea mult. Verifică serviciile de localizare și încearcă din nou."
        elif isinstance(exc,LocationDnsError): text="Nu se poate rezolva numele serviciului de localizare (eroare DNS). Verifică accesul la internet și DNS-ul."
        elif isinstance(exc,LocationInternetError): text="Există rețea locală, dar serviciul de localizare nu poate fi atins. Verifică accesul real la internet, proxy-ul sau firewall-ul."
        elif isinstance(exc,LocationTlsError): text="Conexiunea securizată la serviciul de localizare a eșuat deoarece certificatul TLS nu este valid."
        elif isinstance(exc,LocationHttpError): text=f"Serviciul de localizare a răspuns cu o eroare HTTP.\n\n{exc}"
        elif isinstance(exc,LocationResponseError): text=f"Serviciul de localizare a trimis un răspuns invalid.\n\n{exc}"
        elif isinstance(exc,LocationUnavailableError) and str(exc)=="Platformă nesuportată": text="Localizarea Windows nu este disponibilă pe această platformă. Poți introduce coordonatele manual."
        else: text="Locația nu a putut fi determinată.\n\nPoți introduce manual latitudinea și longitudinea, apoi poți apăsa „Recalculează locatorul”."
        messagebox.showerror("Localizare",text,parent=self)
    def save(self) -> None:
        values={name:var.get().strip() for name,var in self.vars.items()}
        try:
            for key in ("default_power_w","latitude","longitude","location_accuracy_m"): values[key]=float(values[key]) if values[key] else None
            if values["default_power_w"] is not None and values["default_power_w"]<=0: raise ValueError("Puterea implicită trebuie să fie pozitivă.")
            if values["latitude"] is not None: coordinates_to_maidenhead(values["latitude"],values["longitude"])
        except (ValueError,TypeError) as exc: messagebox.showerror("Eroare",str(exc),parent=self); return
        values["callsign"]=normalize_callsign(values["callsign"]); values["full_name"]=normalize_name(values["full_name"]); values["club_callsign"]=normalize_callsign(values["club_callsign"])
        values["maidenhead_locator"]=values["grid_square"]
        values["location_updated_at"]=getattr(self,"_detected_at","") or (datetime.now(timezone.utc).isoformat() if values["latitude"] is not None else "")
        self.db.save_operator_profile(OperatorProfile(**values,notes=self.notes.get("1.0","end-1c"))); messagebox.showinfo("Date operator","Datele operatorului au fost salvate.",parent=self)
    def reset(self) -> None:
        if messagebox.askyesno("Confirmare","Sigur doriți resetarea datelor operatorului?",parent=self): self.db.save_operator_profile(OperatorProfile()); self.load_profile()
