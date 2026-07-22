"""Immutable data exchanged by the propagation-map services and UI."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class SpaceWeatherData:
    kp_index: float | None; a_index: float | None; solar_flux: float | None
    sunspot_number: float | None; radio_blackout_level: str | None
    source: str; observed_at_utc: datetime; fetched_at_utc: datetime

@dataclass(frozen=True)
class PropagationMapRequest:
    latitude: float; longitude: float; maidenhead_locator: str; band: str
    frequency_mhz: float | None; mode: str | None; power_w: float | None
    prediction_time_utc: datetime

@dataclass(frozen=True)
class BandCondition:
    rating: str; score: float; summary: str; warnings: tuple[str, ...] = ()

@dataclass(frozen=True)
class PropagationMapResult:
    image_path: str; band: str; generated_at_utc: datetime
    data_observed_at_utc: datetime | None; source_description: str
    confidence: str; is_cached: bool; warnings: tuple[str, ...] = ()
