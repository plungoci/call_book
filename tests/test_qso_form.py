"""Regression tests for construction and lifecycle of the Qt QSO form."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:
    # Headless CI without PySide6 installed: the class-level skipUnless below
    # disables every test in this module instead of failing at import time.
    QApplication = None  # type: ignore[assignment, misc]

if QApplication is not None:
    from call_book.config import load_config
    from call_book.database import Database
    from call_book.models import QSO
    from call_book.ui.main_window import MainWindow
    from call_book.ui.qso_form import FIELD_GROUPS, FIELD_KEYS, LABELS, QSOForm, validate_field_labels


@unittest.skipUnless(QApplication is not None, "PySide6 is required for Qt UI tests")
class QSOFormTests(unittest.TestCase):
    app: Any = None

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.form = QSOForm(lambda: [])

    def test_all_form_fields_have_exactly_one_label(self):
        self.assertEqual(len(FIELD_KEYS), len(set(FIELD_KEYS)))
        self.assertEqual(set(FIELD_KEYS), set(LABELS))
        validate_field_labels()

    def test_grid_square_is_in_connection_group_after_operator_name(self):
        field_groups = dict(FIELD_GROUPS)

        self.assertEqual(
            field_groups["Legătură"].index("grid_square"),
            field_groups["Legătură"].index("operator_name") + 1,
        )

    def test_form_starts_when_a_field_translation_is_missing(self):
        """A translation mistake must not make the whole application unusable."""
        with patch.dict(LABELS, {}, clear=True):
            form = QSOForm(lambda: [])

        self.assertIn("callsign", form.fields)

    def test_callsign_field_has_label_widget_and_helpful_tooltip(self):
        self.assertEqual(LABELS["callsign"], "Indicativ")
        self.assertIn("callsign", self.form.fields)
        self.assertIn("indicativul", self.form.fields["callsign"].toolTip().lower())

    def test_live_formatting_preserves_cursor_position(self):
        callsign = self.form.fields["callsign"]
        callsign.setText("yo8abc")
        callsign.setCursorPosition(3)
        callsign.textEdited.emit(callsign.text())
        self.assertEqual(callsign.text(), "YO8ABC")
        self.assertEqual(callsign.cursorPosition(), 3)

        operator_name = self.form.fields["operator_name"]
        operator_name.setText("ion popescu")
        operator_name.setCursorPosition(4)
        operator_name.textEdited.emit(operator_name.text())
        self.assertEqual(operator_name.text(), "Ion Popescu")
        self.assertEqual(operator_name.cursorPosition(), 4)

    def test_grid_square_is_always_capitalized(self):
        grid_square = self.form.fields["grid_square"]
        grid_square.setText("kn34bk")
        grid_square.setCursorPosition(4)
        grid_square.textEdited.emit(grid_square.text())

        self.assertEqual(grid_square.text(), "KN34BK")
        self.assertEqual(grid_square.cursorPosition(), 4)

        self.form.set_text("grid_square", "jo62qn")
        self.assertEqual(grid_square.text(), "JO62QN")
        self.form.set_text("frequency_mhz", "145.500")
        self.assertEqual(self.form.value().grid_square, "JO62QN")

    def test_callsign_can_be_loaded_serialized_and_cleared(self):
        qso = QSO(id=7, callsign="YO3ABC", frequency_mhz=145.5, mode="FM")
        self.form.load(qso)
        self.assertEqual(self.form.text("callsign"), "YO3ABC")
        self.assertEqual(self.form.value().callsign, "YO3ABC")

        self.form.new()
        self.assertEqual(self.form.text("callsign"), "")

    def test_new_qso_keeps_the_previously_selected_propagation_mode(self):
        self.form.set_text("propagation_mode", "Satelit")

        self.form.new()

        self.assertEqual(self.form.text("propagation_mode"), "Satelit")

    def test_band_change_suggests_propagation_mode_for_new_qso(self):
        # Regression test: suggest_propagation_mode/PropagationSuggestionState
        # exist and are unit-tested but were never wired into the form after
        # the Tkinter-to-PySide6 migration, so this never actually ran.
        self.form.set_text("band", "20m")

        self.assertEqual(self.form.text("propagation_mode"), "F2")

    def test_manually_selected_propagation_mode_is_protected_from_band_changes(self):
        self.form.set_text("propagation_mode", "EME (Moonbounce)")

        self.form.set_text("band", "20m")

        self.assertEqual(self.form.text("propagation_mode"), "EME (Moonbounce)")

    def test_selecting_repeater_overrides_manual_propagation_mode(self):
        def repeaters():
            return [{"id": 3, "name": "YO3RPT", "output_frequency_mhz": 145.6, "mode": "FM"}]

        form = QSOForm(repeaters)
        form.set_text("propagation_mode", "EME (Moonbounce)")

        form.fields["repeater"].setCurrentIndex(1)

        self.assertEqual(form.text("propagation_mode"), "Repeater")

    def test_loading_an_existing_qso_protects_its_propagation_mode(self):
        qso = QSO(id=7, callsign="YO3ABC", frequency_mhz=145.5, mode="FM", propagation_mode="EME (Moonbounce)")

        self.form.load(qso)
        self.form.set_text("band", "20m")

        self.assertEqual(self.form.text("propagation_mode"), "EME (Moonbounce)")

    def test_repeater_dropdown_matches_mode_and_propagation_mode_behavior(self):
        # Repeater must open/select/close exactly like Mode and Propagation
        # mode: a plain, non-editable QComboBox that opens on any click.
        repeater = self.form.fields["repeater"]
        mode = self.form.fields["mode"]
        propagation_mode = self.form.fields["propagation_mode"]

        self.assertFalse(repeater.isEditable())
        self.assertEqual(repeater.isEditable(), mode.isEditable())
        self.assertEqual(repeater.isEditable(), propagation_mode.isEditable())

    def test_repeater_dropdown_is_populated_on_form_creation(self):
        def repeaters():
            return [
                {
                    "id": 12,
                    "name": "YO3RPT",
                    "output_frequency_mhz": 145.675,
                    "mode": "C4FM",
                }
            ]

        form = QSOForm(repeaters)

        repeater = form.fields["repeater"]
        self.assertEqual(repeater.count(), 2)
        self.assertEqual(repeater.itemText(1), "12 — YO3RPT")

        repeater.setCurrentIndex(1)
        self.assertEqual(form.text("frequency_mhz"), "145.675")
        self.assertEqual(form.text("mode"), "C4FM")

    def test_loaded_callsign_can_be_edited_and_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "logbook.db")
            qso = QSO(callsign="YO3ABC", frequency_mhz=145.5, mode="FM")
            qso_id = database.save_qso(qso)

            self.form.load(database.get_qso(qso_id))
            self.form.set_text("callsign", "YO8XYZ")
            database.save_qso(self.form.value())

            self.assertEqual(database.get_qso(qso_id).callsign, "YO8XYZ")

    def test_main_window_constructs_with_qso_form(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Database(Path(directory) / "logbook.db"), load_config())
            self.assertIsInstance(window.form, QSOForm)
            window.close()

    def test_show_propagation_panel_false_hides_the_tab(self):
        # Regression test: this documented config setting had no effect at all
        # before; the "Propagare" tab was always shown regardless of its value.
        with tempfile.TemporaryDirectory() as directory:
            config = load_config()
            config["show_propagation_panel"] = "false"
            window = MainWindow(Database(Path(directory) / "logbook.db"), config)

            self.assertIsNone(window.propagation_panel)
            tab_titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
            self.assertNotIn("Propagare", tab_titles)

            window.close()

    def test_propagation_auto_refresh_timer_starts_with_configured_interval(self):
        # Regression test: propagation_auto_refresh_minutes was read into
        # config.json and shown in Setări → Setări propagare, but nothing
        # ever scheduled a recurring refresh from it.
        with tempfile.TemporaryDirectory() as directory:
            config = load_config()
            config["propagation_auto_refresh_minutes"] = "30"
            window = MainWindow(Database(Path(directory) / "logbook.db"), config)

            self.assertTrue(window.propagation_auto_refresh_timer.isActive())
            self.assertEqual(window.propagation_auto_refresh_timer.interval(), 30 * 60 * 1000)

            window.close()

    def test_propagation_auto_refresh_disabled_for_interval_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            config = load_config()
            config["propagation_auto_refresh_minutes"] = "0"
            window = MainWindow(Database(Path(directory) / "logbook.db"), config)

            self.assertFalse(window.propagation_auto_refresh_timer.isActive())

            window.close()

    def test_propagation_auto_refresh_disabled_when_panel_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            config = load_config()
            config["show_propagation_panel"] = "false"
            config["propagation_auto_refresh_minutes"] = "15"
            window = MainWindow(Database(Path(directory) / "logbook.db"), config)

            self.assertFalse(window.propagation_auto_refresh_timer.isActive())

            window.close()

    def test_automatic_propagation_refresh_reschedules_itself(self):
        with tempfile.TemporaryDirectory() as directory:
            config = load_config()
            config["propagation_auto_refresh_minutes"] = "10"
            window = MainWindow(Database(Path(directory) / "logbook.db"), config)
            window.propagation_auto_refresh_timer.stop()

            window._automatic_propagation_refresh()

            self.assertTrue(window.propagation_auto_refresh_timer.isActive())
            self.assertEqual(window.propagation_auto_refresh_timer.interval(), 10 * 60 * 1000)

            window.close()

    def test_saving_propagation_settings_reschedules_the_timer(self):
        with tempfile.TemporaryDirectory() as directory:
            config = load_config()
            config["propagation_auto_refresh_minutes"] = "10"
            window = MainWindow(Database(Path(directory) / "logbook.db"), config)

            window.app_config["propagation_auto_refresh_minutes"] = "60"
            window._schedule_propagation_auto_refresh()

            self.assertEqual(window.propagation_auto_refresh_timer.interval(), 60 * 60 * 1000)

            window.close()


if __name__ == "__main__":
    unittest.main()
