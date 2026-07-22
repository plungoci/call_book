"""Qt QSO editor; presentation only, with domain validation kept in controllers."""
from __future__ import annotations
from datetime import datetime, timezone
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QGridLayout, QGroupBox, QLineEdit, QTextEdit, QVBoxLayout, QWidget
from models import QSO
from propagation import PROPAGATION_MODES
from services.band_detector import BandDetector
from services.propagation_service import PROPAGATION_UNKNOWN
from validators import format_name_input, normalize_callsign
MODES=("FM","AM","SSB","USB","LSB","CW","RTTY","FT8","FT4","PSK31","DIGITAL","MSK144","EchoLink","AllStar","DMR","D-STAR","C4FM","Internet Gateway")
QSL=("NOT_SENT","SENT","RECEIVED","CONFIRMED")
FORM_FIELDS=(("Indicativ","callsign"),("Nume","operator_name"),("Repetor","repeater"),("Frecvență MHz","frequency_mhz"),("Bandă","band"),("Mod","mode"),("RST trimis","rst_sent"),("RST primit","rst_received"),("Locator","grid_square"),("Putere W","power_w"),("QSL","qsl_status"),("Început UTC","qso_start_utc"),("Sfârșit UTC","qso_end_utc"),("Propagare","propagation_mode"),("Satelit","satellite_name"),("Mod uplink","uplink_mode"),("Mod downlink","downlink_mode"),("Distanță km","distance_km"),("Azimut °","azimuth_deg"))
class QSOForm(QGroupBox):
    contextChanged=Signal(str,str)
    def __init__(self, repeaters, default_power_w=None):
        super().__init__("QSO · toate orele sunt UTC"); self.repeaters=repeaters; self.default_power_w=default_power_w; self.qso_id=None; self.fields={}; self._loading=False
        layout=QVBoxLayout(self); grid=QGridLayout(); layout.addLayout(grid); labels=dict(FORM_FIELDS)
        groups=(("Legătură",("callsign","operator_name","frequency_mhz","band","mode","repeater","propagation_mode")),("Raport și confirmare",("rst_sent","rst_received","power_w","qsl_status","grid_square")),("Timp și traseu",("qso_start_utc","qso_end_utc","satellite_name","uplink_mode","downlink_mode","distance_km","azimuth_deg")))
        for col,(title,keys) in enumerate(groups):
            box=QGroupBox(title); form=QFormLayout(box); grid.addWidget(box,0,col)
            for key in keys:
                widget=QComboBox() if key in {"repeater","mode","qsl_status","propagation_mode"} else QLineEdit()
                if isinstance(widget,QComboBox):
                    widget.setEditable(key=="repeater"); widget.addItems({"mode":MODES,"qsl_status":QSL,"propagation_mode":PROPAGATION_MODES}.get(key,[]))
                    if key=="repeater": widget.currentTextChanged.connect(self._repeater)
                widget.setToolTip(f"Valoarea {labels[key].lower()} pentru acest QSO."); form.addRow(labels[key],widget); self.fields[key]=widget
        self.notes=QTextEdit(); self.notes.setFixedHeight(72); self.notes.setToolTip("Informații suplimentare despre QSO."); layout.addWidget(self.notes)
        self._line("callsign").editingFinished.connect(lambda:self._format("callsign",normalize_callsign)); self._line("operator_name").editingFinished.connect(lambda:self._format("operator_name",format_name_input)); self._line("frequency_mhz").textChanged.connect(self._frequency_changed); self._line("band").textChanged.connect(self._context)
        self.new()
    def _line(self,key): return self.fields[key]
    def text(self,key): return self.fields[key].currentText() if isinstance(self.fields[key],QComboBox) else self.fields[key].text()
    def set_text(self,key,value):
        w=self.fields[key]; (w.setCurrentText(str(value)) if isinstance(w,QComboBox) else w.setText(str(value)))
    def _format(self,key,formatter): self.set_text(key,formatter(self.text(key)))
    def _frequency_changed(self,value):
        if self._loading:return
        try: band=BandDetector.frequency_to_band(float(value))
        except ValueError: return
        if band: self.set_text("band",band)
        self._context()
    def _context(self,*_):
        if not self._loading:self.contextChanged.emit(self.text("band"),self.text("frequency_mhz"))
    def _repeater(self,text):
        if self._loading or not text:return
        rid=text.split(" ")[0]; r=next((x for x in self.repeaters() if str(x["id"])==rid),None)
        if r: self.set_text("frequency_mhz",r["output_frequency_mhz"]); self.set_text("mode",r["mode"] or "FM")
    def refresh_repeaters(self):
        w=self.fields["repeater"]; current=w.currentText(); w.blockSignals(True); w.clear(); w.addItem(""); w.addItems([f'{r["id"]} — {r["name"]}' for r in self.repeaters()]); w.setCurrentText(current); w.blockSignals(False)
    def new(self):
        self._loading=True; self.qso_id=None
        for key in self.fields:self.set_text(key,"")
        self.set_text("qso_start_utc",datetime.now(timezone.utc).replace(microsecond=0).isoformat()); self.set_text("mode","FM"); self.set_text("qsl_status","NOT_SENT"); self.set_text("propagation_mode",PROPAGATION_UNKNOWN); self.set_text("power_w","" if self.default_power_w is None else f"{self.default_power_w:g}"); self.notes.clear(); self._loading=False; self.fields["callsign"].setFocus()
    def load(self,q):
        self._loading=True; self.qso_id=q.id
        for key in self.fields:
            if key=="repeater": self.set_text(key,f"{q.repeater_id} —" if q.repeater_id else "")
            elif hasattr(q,key): self.set_text(key,getattr(q,key) or "")
        self.notes.setPlainText(q.notes); self._loading=False
    def value(self):
        rep=self.text("repeater").split(" ")[0]; t=self.text
        return QSO(id=self.qso_id,callsign=t("callsign"),operator_name=t("operator_name"),repeater_id=int(rep) if rep.isdigit() else None,frequency_mhz=float(t("frequency_mhz")),band=t("band"),mode=t("mode"),rst_sent=t("rst_sent"),rst_received=t("rst_received"),grid_square=t("grid_square"),power_w=float(t("power_w")) if t("power_w") else None,qsl_status=t("qsl_status"),qso_start_utc=t("qso_start_utc"),qso_end_utc=t("qso_end_utc"),notes=self.notes.toPlainText(),propagation_mode=t("propagation_mode"),satellite_name=t("satellite_name"),uplink_mode=t("uplink_mode"),downlink_mode=t("downlink_mode"),distance_km=float(t("distance_km")) if t("distance_km") else None,azimuth_deg=float(t("azimuth_deg")) if t("azimuth_deg") else None)
