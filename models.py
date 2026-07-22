"""Date models for the radio logbook."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(slots=True)
class QSO:
    callsign: str; qso_start_utc: str; frequency_mhz: float; mode: str
    id: Optional[int] = None; qso_end_utc: Optional[str] = None; band: str = ""
    repeater_id: Optional[int] = None; rst_sent: str = ""; rst_received: str = ""
    operator_name: str = ""; grid_square: str = ""; power_w: Optional[float] = None
    notes: str = ""; qsl_status: str = "NOT_SENT"; created_at: str = ""; updated_at: Optional[str] = None

@dataclass(slots=True)
class Repeater:
    name: str; output_frequency_mhz: float; id: Optional[int] = None
    input_frequency_mhz: Optional[float] = None; shift_mhz: Optional[float] = None
    tone_hz: Optional[float] = None; mode: str = ""; location: str = ""; grid_square: str = ""; notes: str = ""
