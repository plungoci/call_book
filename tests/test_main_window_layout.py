"""Tests for how the main window sizes itself and integrates the DX cluster."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

try:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:
    QApplication = None  # type: ignore[assignment, misc]

if QApplication is not None:
    from call_book.config import DEFAULT_CONFIG, dx_cluster_node, load_config
    from call_book.database import Database
    from call_book.ui.main_window import MainWindow


@unittest.skipUnless(QApplication is not None, "PySide6 is required for Qt UI tests")
class WindowSizingTests(unittest.TestCase):
    app: Any = None

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, config=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        window = MainWindow(Database(Path(directory.name) / "logbook.db"), config or load_config())
        self.addCleanup(window.close)
        return window

    def test_the_window_never_demands_more_than_the_screen_offers(self) -> None:
        # The old fixed 1550x900 minimum made the window unusable on a
        # 1366x768 laptop: it could not be resized to fit the display.
        available = QGuiApplication.primaryScreen().availableGeometry()
        minimum = self._window().minimumSize()
        self.assertLessEqual(minimum.width(), available.width())
        self.assertLessEqual(minimum.height(), available.height())

    def test_the_minimum_size_fits_a_small_laptop_display(self) -> None:
        minimum = self._window().minimumSize()
        self.assertLessEqual(minimum.width(), 1366)
        self.assertLessEqual(minimum.height(), 768)

    def test_the_window_opens_inside_the_available_area(self) -> None:
        available = QGuiApplication.primaryScreen().availableGeometry()
        window = self._window()
        self.assertLessEqual(window.width(), available.width())
        self.assertLessEqual(window.height(), available.height())

    def test_closing_cancels_the_deferred_first_weather_fetch(self) -> None:
        # The deferred refresh used to be a bare QTimer.singleShot, which
        # still fired 1.5s after the window was closed — starting a network
        # call, and a thread, on a panel that was already gone.
        window = self._window()
        window.close()
        self.assertFalse(window.initial_weather_timer.isActive())

    def test_the_log_tab_splits_the_form_from_the_table(self) -> None:
        window = self._window()
        self.assertEqual(window.log_splitter.count(), 2)
        self.assertFalse(window.log_splitter.childrenCollapsible())


@unittest.skipUnless(QApplication is not None, "PySide6 is required for Qt UI tests")
class DxClusterIntegrationTests(unittest.TestCase):
    app: Any = None

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, **overrides):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = load_config() | overrides
        window = MainWindow(Database(Path(directory.name) / "logbook.db"), config)
        self.addCleanup(window.close)
        return window

    def test_the_cluster_tab_is_present_by_default_and_starts_disconnected(self) -> None:
        window = self._window()
        titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        self.assertIn("DX Cluster", titles)
        self.assertIsNotNone(window.dx_cluster_panel)
        self.assertFalse(window.dx_cluster_panel.is_connected)

    def test_the_cluster_tab_can_be_switched_off(self) -> None:
        window = self._window(show_dx_cluster_panel="false")
        titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        self.assertNotIn("DX Cluster", titles)
        self.assertIsNone(window.dx_cluster_panel)

    def test_loading_a_spot_fills_the_form_and_shows_the_log_tab(self) -> None:
        window = self._window()
        window.load_spot_into_form("JA1XYZ", 14.205, "20m", "PM95")
        self.assertEqual(window.form.text("callsign"), "JA1XYZ")
        self.assertEqual(window.form.text("frequency_mhz"), "14.205")
        self.assertEqual(window.form.text("band"), "20m")
        self.assertEqual(window.form.text("grid_square"), "PM95")
        self.assertIs(window.tabs.currentWidget(), window.log)

    def test_loading_a_spot_on_an_unknown_band_keeps_the_detected_band(self) -> None:
        window = self._window()
        window.load_spot_into_form("YO3ABC", 145.5, "Unknown", "")
        self.assertEqual(window.form.text("band"), "2m")

    def test_a_spot_highlights_its_segment_in_the_band_plan(self) -> None:
        window = self._window()
        window.load_spot_into_form("YO3ABC", 145.5, "2m", "")
        self.assertEqual(window.form.band_plan_panel.highlighted_frequency, 145.5)


@unittest.skipUnless(QApplication is not None, "PySide6 is required for Qt UI tests")
class StationPositionTests(unittest.TestCase):
    """Distance and bearing need a position; a locator alone is enough."""

    app: Any = None

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        window = MainWindow(Database(Path(directory.name) / "logbook.db"), load_config())
        self.addCleanup(window.close)
        return window

    def test_detected_coordinates_are_used_when_present(self) -> None:
        window = self._window()
        window.operator_profile.latitude = 45.79
        window.operator_profile.longitude = 24.15
        self.assertEqual(window.station_position(), (45.79, 24.15))

    def test_the_locator_is_used_when_no_coordinates_were_detected(self) -> None:
        window = self._window()
        window.operator_profile.latitude = None
        window.operator_profile.longitude = None
        window.operator_profile.grid_square = "KN25"
        latitude, longitude = window.station_position()
        self.assertAlmostEqual(latitude, 45.5, delta=0.6)
        self.assertAlmostEqual(longitude, 25.0, delta=1.1)

    def test_an_invalid_locator_yields_no_position_instead_of_raising(self) -> None:
        window = self._window()
        window.operator_profile.latitude = None
        window.operator_profile.longitude = None
        window.operator_profile.grid_square = "nu-e-locator"
        window.operator_profile.maidenhead_locator = ""
        self.assertEqual(window.station_position(), (None, None))

    def test_no_position_at_all_is_reported_as_none(self) -> None:
        window = self._window()
        window.operator_profile.latitude = None
        window.operator_profile.longitude = None
        window.operator_profile.grid_square = ""
        window.operator_profile.maidenhead_locator = ""
        self.assertEqual(window.station_position(), (None, None))


@unittest.skipUnless(QApplication is not None, "PySide6 is required for Qt UI tests")
class ClusterConfigTests(unittest.TestCase):
    def test_defaults_are_a_usable_node(self) -> None:
        host, port = dx_cluster_node(DEFAULT_CONFIG)
        self.assertTrue(host)
        self.assertTrue(1 <= port <= 65535)

    def test_a_configured_node_is_used(self) -> None:
        self.assertEqual(
            dx_cluster_node({"dx_cluster_host": "dxc.ve7cc.net", "dx_cluster_port": "23"}),
            ("dxc.ve7cc.net", 23),
        )

    def test_an_invalid_port_falls_back_to_the_default(self) -> None:
        default_port = dx_cluster_node(DEFAULT_CONFIG)[1]
        for value in ("abc", "0", "99999", ""):
            self.assertEqual(dx_cluster_node({"dx_cluster_port": value})[1], default_port, value)


if __name__ == "__main__":
    unittest.main()
