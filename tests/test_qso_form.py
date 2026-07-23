"""Regression tests for construction and lifecycle of the Qt QSO form."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:
    QApplication = None

if QApplication is not None:
    from config import load_config
    from database import Database
    from models import QSO
    from ui.main_window import MainWindow
    from ui.qso_form import FIELD_KEYS, LABELS, QSOForm, validate_field_labels


@unittest.skipUnless(QApplication is not None, "PySide6 is required for Qt UI tests")
class QSOFormTests(unittest.TestCase):
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

    def test_callsign_can_be_loaded_serialized_and_cleared(self):
        qso = QSO(
            id=7,
            callsign="YO3ABC",
            qso_start_utc="2026-01-01T12:00:00+00:00",
            frequency_mhz=145.5,
            mode="FM",
        )
        self.form.load(qso)
        self.assertEqual(self.form.text("callsign"), "YO3ABC")
        self.assertEqual(self.form.value().callsign, "YO3ABC")

        self.form.new()
        self.assertEqual(self.form.text("callsign"), "")

    def test_new_qso_keeps_the_previously_selected_propagation_mode(self):
        self.form.set_text("propagation_mode", "Satelit")

        self.form.new()

        self.assertEqual(self.form.text("propagation_mode"), "Satelit")

    def test_optional_groups_are_hidden_until_their_checkboxes_are_selected(self):
        report_check = self.form.optional_group_checks["Raport și confirmare"]
        route_check = self.form.optional_group_checks["Timp și traseu"]

        self.assertFalse(report_check.isChecked())
        self.assertTrue(self.form.optional_group_boxes["Raport și confirmare"].isHidden())
        self.assertFalse(route_check.isChecked())
        self.assertTrue(self.form.optional_group_boxes["Timp și traseu"].isHidden())

        report_check.setChecked(True)
        route_check.setChecked(True)

        self.assertFalse(self.form.optional_group_boxes["Raport și confirmare"].isHidden())
        self.assertFalse(self.form.optional_group_boxes["Timp și traseu"].isHidden())

    def test_loading_a_qso_keeps_optional_groups_hidden(self):
        qso = QSO(
            id=7,
            callsign="YO3ABC",
            frequency_mhz=145.5,
            mode="FM",
            qso_start_utc="2026-01-01T12:00:00+00:00",
            rst_sent="59",
        )

        self.form.load(qso)

        self.assertFalse(self.form.optional_group_checks["Raport și confirmare"].isChecked())
        self.assertFalse(self.form.optional_group_checks["Timp și traseu"].isChecked())

    def test_repeater_dropdown_is_populated_on_form_creation(self):
        repeaters = lambda: [{
            "id": 12,
            "name": "YO3RPT",
            "output_frequency_mhz": 145.675,
            "mode": "C4FM",
        }]
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
            qso = QSO(
                callsign="YO3ABC",
                qso_start_utc="2026-01-01T12:00:00+00:00",
                frequency_mhz=145.5,
                mode="FM",
            )
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


if __name__ == "__main__":
    unittest.main()
