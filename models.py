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
    my_grid_square: str = ""

@dataclass(slots=True)
class Repeater:
    name: str; output_frequency_mhz: float; id: Optional[int] = None
    input_frequency_mhz: Optional[float] = None; shift_mhz: Optional[float] = None
    tone_hz: Optional[float] = None; mode: str = ""; location: str = ""; grid_square: str = ""; notes: str = ""


@dataclass(slots=True)
class OperatorProfile:
    """Personal details of the owner of this logbook."""

    callsign: str = ""
    full_name: str = ""
    maidenhead_locator: str = ""
    locality: str = ""
    county: str = ""
    country: str = ""
    address: str = ""
    email: str = ""
    phone: str = ""
    radio_equipment: str = ""
    antenna: str = ""
    default_power_w: Optional[float] = None
    radio_club: str = ""
    club_callsign: str = ""
    notes: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy_m: Optional[float] = None
    location_source: str = ""
    location_updated_at: str = ""
    grid_square: str = ""
