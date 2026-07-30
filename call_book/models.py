"""Date models for the radio logbook."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Protocol


class _Row(Protocol):
    """Structural type for sqlite3.Row and plain mappings alike."""

    def keys(self) -> Any: ...
    def __getitem__(self, key: str) -> Any: ...


@dataclass(slots=True)
class QSO:
    callsign: str
    frequency_mhz: float
    mode: str
    id: int | None = None
    band: str = ""
    repeater_id: int | None = None
    operator_name: str = ""
    grid_square: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str | None = None
    my_grid_square: str = ""
    propagation_mode: str = "Necunoscută"
    propagation_notes: str = ""

    @classmethod
    def from_row(cls, row: _Row) -> QSO:
        """Build a QSO from a database row, ignoring extra joined columns (e.g. ``repeater_name``)."""
        known_fields = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in dict(row).items() if key in known_fields})


@dataclass(slots=True)
class Repeater:
    name: str
    output_frequency_mhz: float
    id: int | None = None
    input_frequency_mhz: float | None = None
    shift_mhz: float | None = None
    tone_hz: float | None = None
    mode: str = ""
    location: str = ""
    grid_square: str = ""
    notes: str = ""


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
    default_power_w: float | None = None
    radio_club: str = ""
    club_callsign: str = ""
    notes: str = ""
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy_m: float | None = None
    location_source: str = ""
    location_updated_at: str = ""
    grid_square: str = ""
