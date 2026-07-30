"""Unit tests for QSO.from_row, which replaces __dataclass_fields__ introspection."""

from __future__ import annotations

import unittest

from call_book.models import QSO


class QSOFromRowTests(unittest.TestCase):
    def _row(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = dict(
            id=1,
            callsign="YO3ABC",
            qso_start_utc="2026-01-01T12:00:00+00:00",
            qso_end_utc=None,
            frequency_mhz=145.5,
            band="2m",
            mode="FM",
            repeater_id=None,
            rst_sent="59",
            rst_received="59",
            operator_name="Ion Popescu",
            grid_square="KN34BK",
            my_grid_square="",
            power_w=25.0,
            notes="",
            qsl_status="NOT_SENT",
            created_at="2026-01-01T12:00:00+00:00",
            updated_at=None,
            propagation_mode="Necunoscută",
            satellite_name="",
            uplink_mode="",
            downlink_mode="",
            distance_km=None,
            azimuth_deg=None,
            propagation_notes="",
        )
        values.update(overrides)
        return values

    def test_builds_qso_from_matching_columns(self) -> None:
        qso = QSO.from_row(self._row())
        self.assertEqual(qso.callsign, "YO3ABC")
        self.assertEqual(qso.frequency_mhz, 145.5)
        self.assertEqual(qso.grid_square, "KN34BK")

    def test_ignores_extra_joined_columns(self) -> None:
        row = self._row(repeater_name="YO3RPT")
        qso = QSO.from_row(row)
        self.assertEqual(qso.callsign, "YO3ABC")
        self.assertFalse(hasattr(qso, "repeater_name"))


if __name__ == "__main__":
    unittest.main()
