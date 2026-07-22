"""Business validation and amateur-band helpers."""
from __future__ import annotations
from datetime import datetime
import re
from models import QSO
BAND_RANGES = ((1.8,2.0,"160m"),(3.5,4.0,"80m"),(5.25,5.45,"60m"),(7.0,7.3,"40m"),(10.1,10.15,"30m"),(14.0,14.35,"20m"),(18.068,18.168,"17m"),(21.0,21.45,"15m"),(24.89,24.99,"12m"),(28.0,29.7,"10m"),(50.0,54.0,"6m"),(70.0,71.0,"4m"),(144.0,148.0,"2m"),(430.0,440.0,"70cm"),(1240.0,1300.0,"23cm"))
CALLSIGN_RE = re.compile(r"^[A-Z0-9]+(?:/[A-Z0-9]+)*$")
GRID_RE = re.compile(r"^[A-R]{2}[0-9]{2}(?:[A-X]{2})?(?:[0-9]{2})?$", re.I)
def normalize_callsign(value: str) -> str: return value.strip().upper()
def normalize_name(value: str) -> str:
    """Collapse whitespace and title-case each operator-name word."""
    return " ".join(value.split()).title()
def format_name_input(value: str) -> str:
    """Title-case while preserving one trailing space needed to type another word."""
    return normalize_name(value) + (" " if value and value[-1].isspace() else "")
def validate_callsign(value: str) -> str:
    value=normalize_callsign(value)
    if not value or not CALLSIGN_RE.fullmatch(value) or not any(c.isalpha() for c in value): raise ValueError("Indicativul este obligatoriu și poate conține litere, cifre și '/'.")
    return value
def parse_positive(value: str, label: str) -> float:
    try: number=float(value)
    except (TypeError, ValueError) as exc: raise ValueError(f"{label} trebuie să fie numerică.") from exc
    if number <= 0: raise ValueError(f"{label} trebuie să fie mai mare decât zero.")
    return number
def band_for_frequency(frequency: float) -> str:
    return next((band for low, high, band in BAND_RANGES if low <= frequency <= high), "Unknown")
def parse_utc(value: str) -> datetime:
    result=datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None: raise ValueError("Data/ora UTC trebuie să conțină fusul orar (+00:00).")
    return result
def validate_qso(qso: QSO) -> QSO:
    qso.callsign=validate_callsign(qso.callsign)
    qso.operator_name=normalize_name(qso.operator_name)
    if qso.frequency_mhz <= 0: raise ValueError("Frecvența trebuie să fie mai mare decât zero.")
    if not qso.mode.strip(): raise ValueError("Selectați un mod.")
    if qso.power_w is not None and qso.power_w <= 0: raise ValueError("Puterea trebuie să fie pozitivă.")
    if qso.grid_square and not GRID_RE.fullmatch(qso.grid_square.strip()): raise ValueError("Locator Maidenhead invalid.")
    start=parse_utc(qso.qso_start_utc)
    if qso.qso_end_utc and parse_utc(qso.qso_end_utc) < start: raise ValueError("Ora de sfârșit nu poate preceda începutul.")
    qso.band=qso.band or band_for_frequency(qso.frequency_mhz)
    return qso
