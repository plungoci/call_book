"""Regression tests for the repeater management dialog."""

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
    from call_book.database import Database
    from call_book.ui.repeater_window import RepeaterWindow


@unittest.skipUnless(QApplication is not None, "PySide6 is required for Qt UI tests")
class RepeaterWindowTests(unittest.TestCase):
    app: Any = None

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_empty_name_is_rejected_without_saving(self):
        # Regression test: the error message always claimed name and output
        # frequency were required, but only the frequency was actually checked.
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "logbook.db")
            window = RepeaterWindow(None, db, lambda: None)
            window.fields["output_frequency_mhz"].setText("145.600")

            # QMessageBox.critical() would otherwise block on a real modal exec().
            with patch("call_book.ui.repeater_window.QMessageBox.critical") as critical:
                window.save()
                critical.assert_called_once()

            self.assertEqual(db.list_repeaters(), [])
            window.close()

    def test_valid_repeater_is_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "logbook.db")
            window = RepeaterWindow(None, db, lambda: None)
            window.fields["name"].setText("YO3RPT")
            window.fields["output_frequency_mhz"].setText("145.600")

            window.save()

            rows = db.list_repeaters()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "YO3RPT")
            window.close()


if __name__ == "__main__":
    unittest.main()
