"""Headless tests for the static ANCOM amateur band plan reference panel."""

from __future__ import annotations

import os
import unittest

from PySide6.QtWidgets import QApplication

from call_book.services.band_plan import (
    AMATEUR_SEGMENTS,
    SHARED_SEGMENTS,
    band_labels,
    parse_frequency_range,
    segments_for_frequency,
)
from call_book.ui.band_plan_panel import BandPlanPanel
from call_book.validators import BAND_RANGES
from tests.support import require

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


class BandPlanBoundsTests(unittest.TestCase):
    def test_every_segment_exposes_numeric_bounds(self) -> None:
        for entry in AMATEUR_SEGMENTS:
            start, end = entry.bounds_mhz
            self.assertLess(start, end, entry.frequency_range)

    def test_bounds_are_parsed_from_the_displayed_text(self) -> None:
        self.assertEqual(parse_frequency_range("1.81–1.83 MHz"), (1.81, 1.83))
        # Footnote markers from the source table must not confuse the parser.
        self.assertEqual(parse_frequency_range("70–70.3 MHz(2)"), (70.0, 70.3))

    def test_an_unparsable_range_is_rejected_rather_than_guessed(self) -> None:
        with self.assertRaises(ValueError):
            parse_frequency_range("undeva prin 40m")

    def test_segments_for_frequency_finds_the_containing_segment(self) -> None:
        self.assertEqual([s.frequency_range for s in segments_for_frequency(145.5)], ["144.4–146 MHz"])
        self.assertEqual(segments_for_frequency(101.1), ())

    def test_band_labels_drop_footnote_markers_and_duplicates(self) -> None:
        labels = band_labels()
        self.assertEqual(len(labels), len(set(labels)))
        self.assertIn("60m", labels)
        self.assertNotIn("60m**", labels)


class BandPlanPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QApplication.instance() or QApplication([])
        self.panel = BandPlanPanel()

    def test_one_table_lists_every_segment_once(self) -> None:
        # The panel used to show the shared segments a second time in their
        # own table; they are a column here instead.
        self.assertEqual(self.panel.table.rowCount(), len(AMATEUR_SEGMENTS))
        first = AMATEUR_SEGMENTS[0]
        self.assertEqual(require(self.panel.table.item(0, 0)).text(), first.band)
        self.assertEqual(require(self.panel.table.item(0, 1)).text(), first.frequency_range)

    def test_shared_column_names_the_non_amateur_codes_only(self) -> None:
        shared_row = next(i for i, s in enumerate(AMATEUR_SEGMENTS) if s.is_shared_with_government)
        text = require(self.panel.table.item(shared_row, 3)).text()
        self.assertNotIn("NG", text.split(", "))
        self.assertTrue(text)

    def test_exclusive_segments_say_so_instead_of_showing_an_empty_cell(self) -> None:
        exclusive_row = next(i for i, s in enumerate(AMATEUR_SEGMENTS) if not s.is_shared_with_government)
        self.assertEqual(require(self.panel.table.item(exclusive_row, 3)).text(), "exclusiv radioamatori")

    def test_shared_only_filter_matches_the_shared_segments(self) -> None:
        self.panel.shared_only.setChecked(True)
        self.assertEqual(self.panel.table.rowCount(), len(SHARED_SEGMENTS))
        self.assertTrue(all(s.is_shared_with_government for s in self.panel.visible_segments()))

    def test_band_filter_narrows_to_one_band(self) -> None:
        self.panel.band_filter.setCurrentText("70cm")
        self.assertTrue(self.panel.visible_segments())
        self.assertTrue(all(s.band_label == "70cm" for s in self.panel.visible_segments()))

    def test_search_matches_frequency_text(self) -> None:
        self.panel.search.setText("144")
        self.assertTrue(self.panel.visible_segments())
        self.assertTrue(all("144" in s.frequency_range for s in self.panel.visible_segments()))

    def test_filters_combine(self) -> None:
        self.panel.band_filter.setCurrentText("70cm")
        self.panel.shared_only.setChecked(True)
        self.assertTrue(
            all(s.band_label == "70cm" and s.is_shared_with_government for s in self.panel.visible_segments())
        )

    def test_highlighting_a_frequency_reports_the_segment_in_use(self) -> None:
        self.panel.highlight_frequency(145.5)
        self.assertIn("2m", self.panel.summary.text())
        self.assertIn("144.4–146 MHz", self.panel.summary.text())

    def test_highlighting_a_frequency_outside_the_table_says_so(self) -> None:
        self.panel.highlight_frequency(101.1)
        self.assertIn("nu este într-un segment listat", self.panel.summary.text())

    def test_highlighting_ignores_text_that_is_not_a_frequency(self) -> None:
        self.panel.highlight_frequency("")
        self.assertIsNone(self.panel.highlighted_frequency)
        self.panel.highlight_frequency("abc")
        self.assertIsNone(self.panel.highlighted_frequency)

    def test_panel_does_not_demand_a_wide_window(self) -> None:
        # The fixed-size tables it replaced are what forced a 1550px window.
        self.assertLessEqual(self.panel.minimumSizeHint().width(), 320)
