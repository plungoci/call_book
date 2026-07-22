"""Immutable data exchanged by space-weather services and UI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SpaceWeatherData:
    kp_index: float | None
    a_index: float | None
    solar_flux: float | None
    sunspot_number: float | None
    radio_blackout_level: str | None
    source: str
    observed_at_utc: datetime
    fetched_at_utc: datetime
    xray_flux: float | None = None
    proton_flux: float | None = None
    electron_flux: float | None = None
    auroral_activity: float | None = None
    solar_wind_speed: float | None = None
    solar_wind_density: float | None = None
    bz: float | None = None


@dataclass(frozen=True)
class BandCondition:
    rating: str
    score: float
    summary: str
    warnings: tuple[str, ...] = ()
