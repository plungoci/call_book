"""Propagation vocabulary and ADIF mappings, kept separate for future calculations."""
from __future__ import annotations

PROPAGATION_MODES = (
    "Necunoscută", "Directă", "Repeater", "Satelit", "EME (Moonbounce)",
    "Meteor Scatter", "Troposcatter", "Tropospheric Ducting", "Sporadic-E",
    "F2", "Aurora", "Aurora-E", "NVIS", "Backscatter", "Aircraft Scatter",
    "Rain Scatter", "Ionoscatter", "MSK144", "QO-100", "Internet Gateway",
    "EchoLink", "AllStar", "D-STAR", "DMR", "C4FM", "FreeDV", "Altele",
)

# ADIF PROP_MODE values where the standard defines an equivalent.  The remaining
# local descriptions stay available in Excel and are intentionally not exported.
ADIF_PROPAGATION_MODES = {
    "Directă": "DIRECT", "Repeater": "RPT", "Satelit": "SAT",
    "EME (Moonbounce)": "EME", "Meteor Scatter": "MS", "Troposcatter": "TR",
    "Sporadic-E": "ES", "F2": "F2", "Aurora": "AUR", "Aurora-E": "AUE",
    "NVIS": "NVIS", "Backscatter": "BS", "Aircraft Scatter": "ARS",
    "Rain Scatter": "RS", "Ionoscatter": "IS", "Internet Gateway": "INTERNET",
}

SATELLITE_PROPAGATION = "Satelit"
QO100_PROPAGATION = "QO-100"
