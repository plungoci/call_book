"""Headless tests for the DX cluster panel: geocoding, filters and selection."""

from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime

from PySide6.QtWidgets import QApplication, QTableWidget

from call_book.services.dx_cluster import parse_spot
from call_book.ui.dx_cluster_panel import COLUMNS, MAX_SPOTS, DxClusterPanel
from tests.support import require

NOW = datetime(2026, 9, 10, 18, 40, tzinfo=UTC)
SIBIU = (45.79, 24.15)
SPOT_LINES = (
    "DX de HA8TKS:     14205.0  JA1XYZ       Loud here                      1832Z",
    "DX de EA5XXX:      7005.0  EA8ZZZ       CQ CQ                          1834Z",
    "DX de DL1ABC:    144300.0  YO2XYZ/P     tropo KN05os                   1839Z",
    "DX de YO9ABC:     28500.0  QQ1QQ        prefix necunoscut              1840Z",
)


def column(name: str) -> int:
    return COLUMNS.index(name)


def cell(table: QTableWidget, row: int, name: str) -> str:
    """The text shown in one cell, by column name rather than index."""
    return require(table.item(row, column(name))).text()


class DxClusterPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.panel = DxClusterPanel(lambda: SIBIU, lambda: "YO3TEST", lambda: ("127.0.0.1", 8000))
        self.addCleanup(self.panel.shutdown)
        for line in SPOT_LINES:
            self.panel.add_spot(require(parse_spot(line, NOW)))

    def test_constructing_the_panel_opens_no_connection(self) -> None:
        self.assertFalse(self.panel.is_connected)
        self.assertIsNone(self.panel.client)

    def test_newest_spot_is_listed_first(self) -> None:
        self.assertEqual(self.panel.table.rowCount(), len(SPOT_LINES))
        self.assertEqual(cell(self.panel.table, 0, "Indicativ"), "QQ1QQ")

    def test_a_prefix_places_the_spot_at_its_entity(self) -> None:
        row = next(r for r in range(self.panel.table.rowCount()) if cell(self.panel.table, r, "Indicativ") == "JA1XYZ")
        self.assertEqual(cell(self.panel.table, row, "Entitate"), "Japonia")
        self.assertIn("km", cell(self.panel.table, row, "Distanță"))
        self.assertIn("NE", cell(self.panel.table, row, "Azimut"))

    def test_a_locator_in_the_comment_gives_a_precise_position(self) -> None:
        _, found = next(pair for pair in self.panel.spots if pair[0].dx_call == "YO2XYZ/P")
        location = require(found)
        self.assertTrue(location.is_precise)
        self.assertEqual(location.locator, "KN05OS")

    def test_an_unknown_prefix_shows_no_invented_distance(self) -> None:
        row = next(r for r in range(self.panel.table.rowCount()) if cell(self.panel.table, r, "Indicativ") == "QQ1QQ")
        self.assertEqual(cell(self.panel.table, row, "Entitate"), "necunoscut")
        self.assertEqual(cell(self.panel.table, row, "Distanță"), "—")

    def test_a_repeated_spot_is_not_listed_twice(self) -> None:
        self.panel.add_spot(require(parse_spot(SPOT_LINES[0], NOW)))
        self.assertEqual(self.panel.table.rowCount(), len(SPOT_LINES))

    def test_band_filter_learns_the_bands_that_arrive(self) -> None:
        bands = {self.panel.band_filter.itemText(i) for i in range(self.panel.band_filter.count())}
        self.assertLessEqual({"20m", "40m", "2m", "10m"}, bands)
        self.panel.band_filter.setCurrentText("2m")
        self.assertEqual([spot.dx_call for spot, _ in self.panel.visible_spots()], ["YO2XYZ/P"])

    def test_continent_filter_uses_the_geocoded_entity(self) -> None:
        self.panel.continent_filter.setCurrentText("AS")
        self.assertEqual([spot.dx_call for spot, _ in self.panel.visible_spots()], ["JA1XYZ"])

    def test_search_matches_callsign_entity_and_comment(self) -> None:
        for text, expected in (("ea8", "EA8ZZZ"), ("japonia", "JA1XYZ"), ("tropo", "YO2XYZ/P")):
            self.panel.search.setText(text)
            self.assertEqual([spot.dx_call for spot, _ in self.panel.visible_spots()], [expected], text)

    def test_located_only_hides_spots_without_a_position(self) -> None:
        self.panel.located_only.setChecked(True)
        self.assertNotIn("QQ1QQ", [spot.dx_call for spot, _ in self.panel.visible_spots()])

    def test_clearing_empties_the_table(self) -> None:
        self.panel.clear_spots()
        self.assertEqual(self.panel.table.rowCount(), 0)
        self.assertEqual(self.panel.spots, [])

    def test_the_stored_list_is_capped(self) -> None:
        for index in range(MAX_SPOTS + 20):
            self.panel.add_spot(require(parse_spot(f"DX de YO9ABC:  {14000 + index}.0  YO{index}AA  x  1840Z", NOW)))
        self.assertEqual(len(self.panel.spots), MAX_SPOTS)

    def test_selecting_a_spot_emits_what_the_qso_form_needs(self) -> None:
        emitted = []
        self.panel.spotSelected.connect(lambda *values: emitted.append(values))
        row = next(
            r for r in range(self.panel.table.rowCount()) if cell(self.panel.table, r, "Indicativ") == "YO2XYZ/P"
        )
        self.panel.table.selectRow(row)
        self.panel._use_selected_spot()
        self.assertEqual(emitted, [("YO2XYZ/P", 144.3, "2m", "KN05OS")])

    def test_selecting_nothing_emits_nothing(self) -> None:
        emitted = []
        self.panel.spotSelected.connect(lambda *values: emitted.append(values))
        self.panel.table.clearSelection()
        self.panel._use_selected_spot()
        self.assertEqual(emitted, [])

    def test_connecting_without_a_callsign_reports_it_instead_of_dialling(self) -> None:
        panel = DxClusterPanel(lambda: SIBIU, lambda: "", lambda: ("127.0.0.1", 8000))
        self.addCleanup(panel.shutdown)
        panel.connect_to_node()
        self.assertFalse(panel.is_connected)
        self.assertIn("indicativul", panel.status.text())

    def test_distances_need_a_station_position(self) -> None:
        panel = DxClusterPanel(lambda: (None, None), lambda: "YO3TEST", lambda: ("127.0.0.1", 8000))
        self.addCleanup(panel.shutdown)
        panel.add_spot(require(parse_spot(SPOT_LINES[0], NOW)))
        self.assertEqual(cell(panel.table, 0, "Distanță"), "—")
        self.assertEqual(cell(panel.table, 0, "Entitate"), "Japonia")
