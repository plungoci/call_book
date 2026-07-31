"""Headless tests for the static ANCOM amateur band plan reference panel."""

from __future__ import annotations

import os
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from call_book.services.band_plan import AMATEUR_SEGMENTS, SHARED_SEGMENTS
from call_book.ui.band_plan_panel import BandPlanPanel
from call_book.validators import BAND_RANGES

_KNOWN_BANDS = {band for _, _, band in BAND_RANGES}


class BandPlanDataTests(unittest.TestCase):
    def test_segments_span_160m_to_70cm(self) -> None:
        bands = tuple(entry.band for entry in AMATEUR_SEGMENTS)
        self.assertTrue(bands[0].startswith("160m"))
        self.assertEqual(bands[-1], "70cm")

    def test_segment_bands_match_the_apps_known_band_names(self) -> None:
        # Keeps this reference table from drifting from validators.BAND_RANGES,
        # which is what band/frequency auto-detection elsewhere relies on.
        # Footnote markers (e.g. "60m**") are stripped before comparing.
        for entry in AMATEUR_SEGMENTS:
            self.assertIn(entry.band.rstrip("*"), _KNOWN_BANDS)

    def test_every_segment_permits_amateur_use(self) -> None:
        # ANCOM's amateur table only lists spectrum hams may use; some of it
        # is additionally shared with government use, never exclusively.
        for entry in AMATEUR_SEGMENTS:
            self.assertIn("NG", entry.allocation_status.split("/"))

    def test_shared_segments_are_exactly_the_non_exclusive_ones(self) -> None:
        shared = {(e.band, e.frequency_range) for e in SHARED_SEGMENTS}
        for entry in AMATEUR_SEGMENTS:
            is_shared = (entry.band, entry.frequency_range) in shared
            self.assertEqual(is_shared, entry.allocation_status != "NG")

    def test_shared_segments_are_a_strict_subset(self) -> None:
        self.assertLess(len(SHARED_SEGMENTS), len(AMATEUR_SEGMENTS))
        self.assertTrue(set(SHARED_SEGMENTS).issubset(AMATEUR_SEGMENTS))


class BandPlanPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QApplication.instance() or QApplication([])

    def test_tables_have_one_row_per_segment_and_no_scrollbars(self) -> None:
        panel = BandPlanPanel()
        self.assertEqual(panel.amateur_table.rowCount(), len(AMATEUR_SEGMENTS))
        self.assertEqual(panel.shared_table.rowCount(), len(SHARED_SEGMENTS))
        for table in (panel.amateur_table, panel.shared_table):
            self.assertEqual(table.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.assertEqual(table.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def test_amateur_table_shows_exact_frequency_in_mhz(self) -> None:
        panel = BandPlanPanel()
        first = AMATEUR_SEGMENTS[0]
        self.assertEqual(panel.amateur_table.item(0, 0).text(), first.band)
        self.assertEqual(panel.amateur_table.item(0, 1).text(), first.frequency_range)
        self.assertIn("MHz", first.frequency_range)
        self.assertNotIn("kHz", first.frequency_range)

    def test_shared_table_shows_the_non_amateur_codes_only(self) -> None:
        panel = BandPlanPanel()
        first = SHARED_SEGMENTS[0]
        self.assertEqual(panel.shared_table.item(0, 0).text(), first.band)
        partajat_cu = panel.shared_table.item(0, 2).text()
        self.assertNotIn("NG", partajat_cu.split(", "))
        self.assertTrue(partajat_cu)
