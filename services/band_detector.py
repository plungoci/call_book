"""Conversion between an entered frequency and an amateur-radio band."""
from __future__ import annotations

from validators import band_for_frequency


class BandDetector:
    """Single entry point for automatic band selection in UI code."""

    @staticmethod
    def frequency_to_band(frequency_mhz: float) -> str | None:
        """Return the canonical band, or ``None`` when no known band contains it."""
        band = band_for_frequency(frequency_mhz)
        return None if band == "Unknown" else band
