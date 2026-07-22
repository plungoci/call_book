"""Rules for default QSO propagation suggestions, independent of Tkinter.

The result is a *default suggestion*, not a measurement of radio conditions.
"""
from __future__ import annotations

from dataclasses import dataclass

PROPAGATION_UNKNOWN = "Necunoscută"
PROPAGATION_DIRECT = "Directă"
PROPAGATION_REPEATER = "Repeater"
PROPAGATION_SATELLITE = "Satelit"
PROPAGATION_F2 = "F2"
PROPAGATION_NVIS = "NVIS"
PROPAGATION_SPORADIC_E = "Sporadic-E"
PROPAGATION_METEOR_SCATTER = "Meteor Scatter"
PROPAGATION_GROUND_WAVE = "Ground Wave"
PROPAGATION_TROPOSPHERIC = "Tropospheric"


def normalize_band(band: str | None) -> str | None:
    """Return the canonical band spelling used by the suggestion rules."""
    if not band:
        return None
    value = "".join(band.strip().lower().replace(",", ".").split())
    aliases = {"1,25m": "1.25m", "1.25cm": "1.25cm"}
    return aliases.get(value, value) or None


_BAND_DEFAULTS = {
    "2200m": PROPAGATION_GROUND_WAVE, "630m": PROPAGATION_GROUND_WAVE,
    "160m": PROPAGATION_GROUND_WAVE, "80m": PROPAGATION_NVIS,
    "60m": PROPAGATION_NVIS, "40m": PROPAGATION_NVIS,
    "30m": PROPAGATION_F2, "20m": PROPAGATION_F2, "17m": PROPAGATION_F2,
    "15m": PROPAGATION_F2, "12m": PROPAGATION_F2, "10m": PROPAGATION_F2,
    "6m": PROPAGATION_SPORADIC_E, "4m": PROPAGATION_TROPOSPHERIC,
    "2m": PROPAGATION_DIRECT, "1.25m": PROPAGATION_DIRECT,
    "70cm": PROPAGATION_DIRECT, "33cm": PROPAGATION_DIRECT,
    "23cm": PROPAGATION_DIRECT, "13cm": PROPAGATION_DIRECT,
    "9cm": PROPAGATION_DIRECT, "6cm": PROPAGATION_DIRECT,
    "3cm": PROPAGATION_DIRECT, "1.25cm": PROPAGATION_DIRECT,
}
_FM_DIRECT_BANDS = {"6m", "4m", "2m", "1.25m", "70cm", "23cm"}
_MSK_BANDS = {"6m", "4m", "2m"}
_NETWORK_MODES = {"ECHOLINK": "EchoLink", "ALLSTAR": "AllStar", "DMR": "DMR",
                  "D-STAR": "D-STAR", "C4FM": "C4FM", "INTERNET GATEWAY": "Internet Gateway"}


def suggest_propagation_mode(
    band: str | None, frequency_mhz: float | None = None, mode: str | None = None,
    repeater_selected: bool = False, satellite_selected: bool = False,
) -> str:
    """Suggest propagation using documented priority rules and no external data."""
    del frequency_mhz  # Reserved for callers that already know a frequency.
    normalized_band = normalize_band(band)
    normalized_mode = (mode or "").strip().upper()
    if satellite_selected:
        return PROPAGATION_SATELLITE
    if repeater_selected:
        return PROPAGATION_REPEATER
    if normalized_mode in _NETWORK_MODES:
        return _NETWORK_MODES[normalized_mode]
    if normalized_mode == "MSK144" and normalized_band in _MSK_BANDS:
        return PROPAGATION_METEOR_SCATTER
    if normalized_mode == "FM" and normalized_band in _FM_DIRECT_BANDS:
        return PROPAGATION_DIRECT
    return _BAND_DEFAULTS.get(normalized_band, PROPAGATION_UNKNOWN)


@dataclass
class PropagationSuggestionState:
    """Small UI-agnostic state machine protecting manual propagation choices."""
    manually_selected: bool = False

    def mark_manual(self) -> None:
        self.manually_selected = True

    def reset_for_new_qso(self) -> None:
        self.manually_selected = False

    def load_existing_qso(self) -> None:
        self.manually_selected = True

    def may_apply(self, suggestion: str, force: bool = False) -> bool:
        """Allow significant satellite/repeater context to override a manual value."""
        return force or not self.manually_selected or suggestion in {
            PROPAGATION_SATELLITE, PROPAGATION_REPEATER,
        }

    def mark_automatic(self) -> None:
        self.manually_selected = False
