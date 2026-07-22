"""Regression tests for construction and lifecycle of the Qt QSO form."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

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

    def test_callsign_field_has_label_widget_and_helpful_tooltip(self):
        self.assertEqual(LABELS["callsign"], "Indicativ")
        self.assertIn("callsign", self.form.fields)
        self.assertIn("indicativul", self.form.fields["callsign"].toolTip().lower())

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
