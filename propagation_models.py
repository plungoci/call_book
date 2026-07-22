"""Immutable, provenance-aware data exchanged by weather services and UI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class WeatherValue:
    """One observed value; ``None`` is an explicit unavailable observation."""
    value: float | str | None
    unit: str
    source: str
    observed_at_utc: datetime
    quality: str = "observed"
    status: str = "available"

    @property
    def age_seconds(self) -> int:
        return max(0, int((datetime.now(timezone.utc) - self.observed_at_utc).total_seconds()))


@dataclass(frozen=True)
class SpaceWeatherData:
    # Legacy scalar fields remain so callers do not have to know the aggregation internals.
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
    ap_index: float | None = None
    bt: float | None = None
    solar_wind_temperature: float | None = None
    dynamic_pressure: float | None = None
    values: dict[str, WeatherValue] | None = None
    provider_status: dict[str, str] | None = None

    def measurement(self, name: str) -> WeatherValue | None:
        return (self.values or {}).get(name)


@dataclass(frozen=True)
class BandCondition:
    rating: str
    score: float
    summary: str
    warnings: tuple[str, ...] = ()
    confidence: str = "scăzută"
