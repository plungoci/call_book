"""Tests for UI-independent application use cases and configuration persistence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from application_controller import DuplicateQsoCancelled, LogbookController
from config import DEFAULT_CONFIG, load_config, save_config
from database import Database
from models import QSO


class ApplicationControllerTests(TestCase):
    def _qso(self) -> QSO:
        return QSO(callsign="yo3abc", qso_start_utc=datetime.now(timezone.utc).isoformat(), frequency_mhz=145.5, mode="FM")

    def test_save_normalizes_and_lists_qso_without_tk(self) -> None:
        with TemporaryDirectory() as directory:
            controller = LogbookController(Database(Path(directory) / "logbook.db"))
            identifier, edited = controller.save_qso(self._qso(), lambda _: True)
            self.assertFalse(edited)
            self.assertEqual(controller.list_qsos({})[0].callsign, "YO3ABC")
            self.assertEqual(identifier, controller.list_qsos({})[0].id)

    def test_duplicate_can_be_cancelled_by_presentation_layer(self) -> None:
        with TemporaryDirectory() as directory:
            controller = LogbookController(Database(Path(directory) / "logbook.db"))
            controller.save_qso(self._qso(), lambda _: True)
            with self.assertRaises(DuplicateQsoCancelled): controller.save_qso(self._qso(), lambda _: False)

    def test_config_write_round_trip_keeps_known_defaults(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_config({"show_propagation_panel": "false", "unknown": "discard"}, path)
            self.assertEqual(load_config(path)["show_propagation_panel"], "false")
            self.assertEqual(load_config(path)["export_directory"], DEFAULT_CONFIG["export_directory"])
