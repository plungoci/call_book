"""Local propagation estimates, deliberately not a VOACAP prediction."""
from __future__ import annotations

from datetime import datetime

from propagation_models import BandCondition, SpaceWeatherData

HF_BANDS = ("80m", "40m", "20m", "15m", "10m")
_ALL_HF_BANDS = {"160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"}


def _normalise_band(band: str) -> str:
    return "".join((band or "").lower().replace(",", ".").split())


def evaluate_band_conditions(
    band: str,
    space_weather: SpaceWeatherData,
    timestamp_utc: datetime,
    latitude: float | None = None,
    longitude: float | None = None,
) -> BandCondition:
    """Apply the existing local heuristic to one band and point in time."""
    del latitude, longitude
    normalised_band = _normalise_band(band)
    score = 50.0
    warnings: list[str] = []
    if normalised_band in _ALL_HF_BANDS:
        if space_weather.solar_flux is None:
            warnings.append("SFI indisponibil; estimare redusă")
        else:
            score += (space_weather.solar_flux - 100) * (
                0.45 if normalised_band in {"20m", "17m", "15m", "12m", "10m"} else 0.18
            )
        score -= max(0, (space_weather.kp_index or 2) - 2) * 9
        score -= max(0, (space_weather.a_index or 8) - 8) * 0.7
        if space_weather.radio_blackout_level:
            score -= 25
            warnings.append(f"Blackout radio {space_weather.radio_blackout_level}")
        if normalised_band in {"80m", "40m", "160m"} and 6 <= timestamp_utc.hour <= 18:
            score -= 14
    elif normalised_band == "6m":
        score = 35
        warnings.append("Deschiderile Sporadic-E nu pot fi confirmate numai din indicii solari disponibili.")
    else:
        score = 55
        warnings.append("Rază line-of-sight orientativă; nu este predicție ionosferică.")

    score = max(0, min(100, score))
    rating = (
        "Foarte slabă" if score < 20 else "Slabă" if score < 40 else "Moderată"
        if score < 60 else "Bună" if score < 80 else "Foarte bună"
    )
    return BandCondition(rating, score, f"Estimare simplificată: {rating.lower()} ({score:.0f}/100).", tuple(warnings))


class PropagationEstimator:
    """Calculates compact HF day/night rows using the existing heuristic."""

    def calculate_hf(self, weather: SpaceWeatherData, timestamp_utc: datetime) -> dict[str, tuple[BandCondition, BandCondition]]:
        day = timestamp_utc.replace(hour=12, minute=0, second=0, microsecond=0)
        night = timestamp_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        return {
            band: (evaluate_band_conditions(band, weather, day), evaluate_band_conditions(band, weather, night))
            for band in HF_BANDS
        }
