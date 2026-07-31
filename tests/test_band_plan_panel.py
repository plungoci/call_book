"""Headless tests for the static amateur band plan reference panel."""

from __future__ import annotations

import os
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from call_book.services.band_plan import AMATEUR_BANDS, SHARED_ALLOCATIONS
from call_book.ui.band_plan_panel import BandPlanPanel
from call_book.validators import BAND_RANGES

_KNOWN_BANDS = {band for _, _, band in BAND_RANGES}


class BandPlanDataTests(unittest.TestCase):
    def test_amateur_bands_span_160m_to_70cm_with_no_duplicates(self) -> None:
        bands = tuple(entry.band for entry in AMATEUR_BANDS)
        self.assertEqual(bands[0], "160m")
        self.assertEqual(bands[-1], "70cm")
        self.assertEqual(len(bands), len(set(bands)))

    def test_amateur_bands_match_the_apps_known_band_names(self) -> None:
        # Keeps this reference table from drifting from validators.BAND_RANGES,
        # which is what band/frequency auto-detection elsewhere relies on.
        for entry in AMATEUR_BANDS:
            self.assertIn(entry.band, _KNOWN_BANDS)

    def test_shared_allocations_cover_exactly_the_same_bands(self) -> None:
        amateur_bands = tuple(entry.band for entry in AMATEUR_BANDS)
        shared_bands = tuple(entry.band for entry in SHARED_ALLOCATIONS)
        self.assertEqual(amateur_bands, shared_bands)


class BandPlanPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QApplication.instance() or QApplication([])

    def test_tables_have_one_row_per_band_and_no_scrollbars(self) -> None:
        panel = BandPlanPanel()
        self.assertEqual(panel.amateur_table.rowCount(), len(AMATEUR_BANDS))
        self.assertEqual(panel.shared_table.rowCount(), len(SHARED_ALLOCATIONS))
        for table in (panel.amateur_table, panel.shared_table):
            self.assertEqual(table.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.assertEqual(table.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def test_amateur_table_shows_band_frequency_and_notes(self) -> None:
        panel = BandPlanPanel()
        first = AMATEUR_BANDS[0]
        self.assertEqual(panel.amateur_table.item(0, 0).text(), first.band)
        self.assertEqual(panel.amateur_table.item(0, 1).text(), first.frequency_range)
        self.assertEqual(panel.amateur_table.item(0, 2).text(), first.notes)
