"""Tests for the portable backups used to move a logbook between devices."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from call_book.database import Database
from call_book.models import QSO, OperatorProfile, Repeater
from call_book.transfer import (
    BackupFormatError,
    export_backup,
    import_backup,
    load_backup,
    parse_backup,
)


class TransferBackupTests(TestCase):
    def _database(self, directory: str, name: str = "logbook.db") -> Database:
        return Database(Path(directory) / name)

    def _source_database(self, directory: str) -> Database:
        """A small logbook standing in for the secondary device."""
        database = self._database(directory, "source.db")
        repeater_id = database.save_repeater(Repeater(name="YO5KAE", output_frequency_mhz=145.6875, tone_hz=88.5))
        database.save_qso(QSO(callsign="YO3ABC", frequency_mhz=145.5, mode="FM", band="2m"))
        database.save_qso(
            QSO(
                callsign="YO9XYZ",
                frequency_mhz=145.6875,
                mode="FM",
                band="2m",
                repeater_id=repeater_id,
                operator_name="Ion Popescu",
                grid_square="KN16",
                notes="prin repetor",
                propagation_mode="Repeater",
            )
        )
        database.save_operator_profile(OperatorProfile(callsign="YO5ABC", full_name="Paul Lungoci", latitude=45.8))
        return database

    def test_export_then_import_moves_every_record(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source_database(directory)
            path = export_backup(source, destination=Path(directory) / "backup.json")
            target = self._database(directory)

            summary = import_backup(target, load_backup(path))

            self.assertEqual(summary.imported_qsos, 2)
            self.assertEqual(summary.imported_repeaters, 1)
            self.assertTrue(summary.imported_profile)
            imported = {row["callsign"]: row for row in target.list_qsos({})}
            self.assertEqual(set(imported), {"YO3ABC", "YO9XYZ"})
            self.assertEqual(imported["YO9XYZ"]["operator_name"], "Ion Popescu")
            self.assertEqual(imported["YO9XYZ"]["repeater_name"], "YO5KAE")
            self.assertEqual(target.get_operator_profile().callsign, "YO5ABC")

    def test_imported_qsos_keep_their_original_timestamps(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source_database(directory)
            original = source.list_qsos({})[0]
            path = export_backup(source, destination=Path(directory) / "backup.json")
            target = self._database(directory)

            import_backup(target, load_backup(path))

            imported = target.list_qsos({})[0]
            self.assertEqual(imported["qso_start_utc"], original["qso_start_utc"])
            self.assertEqual(imported["created_at"], original["created_at"])

    def test_importing_the_same_backup_twice_adds_nothing(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source_database(directory)
            path = export_backup(source, destination=Path(directory) / "backup.json")
            target = self._database(directory)
            import_backup(target, load_backup(path))

            summary = import_backup(target, load_backup(path))

            self.assertEqual(summary.imported_qsos, 0)
            self.assertEqual(summary.skipped_qsos, 2)
            self.assertEqual(summary.imported_repeaters, 0)
            self.assertEqual(summary.matched_repeaters, 1)
            self.assertEqual(len(target.list_qsos({})), 2)

    def test_import_keeps_records_already_present_on_this_device(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source_database(directory)
            path = export_backup(source, destination=Path(directory) / "backup.json")
            target = self._database(directory)
            target.save_qso(QSO(callsign="YO2AAA", frequency_mhz=7.1, mode="SSB", band="40m"))
            target.save_operator_profile(OperatorProfile(callsign="YO5XYZ", full_name="Alt Operator"))

            summary = import_backup(target, load_backup(path))

            self.assertFalse(summary.imported_profile)
            self.assertEqual(target.get_operator_profile().callsign, "YO5XYZ")
            self.assertEqual(len(target.list_qsos({})), 3)

    def test_existing_repeater_is_reused_instead_of_duplicated(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source_database(directory)
            path = export_backup(source, destination=Path(directory) / "backup.json")
            target = self._database(directory)
            local_id = target.save_repeater(Repeater(name="yo5kae", output_frequency_mhz=145.6875))

            summary = import_backup(target, load_backup(path))

            self.assertEqual(summary.imported_repeaters, 0)
            self.assertEqual(summary.matched_repeaters, 1)
            self.assertEqual(len(target.list_repeaters()), 1)
            through_repeater = next(row for row in target.list_qsos({}) if row["callsign"] == "YO9XYZ")
            self.assertEqual(through_repeater["repeater_id"], local_id)

    def test_qso_pointing_at_a_missing_repeater_is_still_imported(self) -> None:
        with TemporaryDirectory() as directory:
            document = {
                "format": "call-book-backup",
                "version": 1,
                "qsos": [
                    {
                        "callsign": "YO3ABC",
                        "frequency_mhz": 145.5,
                        "mode": "FM",
                        "repeater_id": 42,
                        "created_at": "2026-01-02T03:04:05+00:00",
                    }
                ],
            }
            target = self._database(directory)

            import_backup(target, parse_backup(document))

            imported = target.list_qsos({})[0]
            self.assertIsNone(imported["repeater_id"])
            self.assertEqual(imported["band"], "2m")

    def test_unrelated_or_broken_files_are_rejected_before_any_write(self) -> None:
        with TemporaryDirectory() as directory:
            target = self._database(directory)
            path = Path(directory) / "not-a-backup.json"
            path.write_text('{"hello": "world"}', encoding="utf-8")
            with self.assertRaises(BackupFormatError):
                load_backup(path)
            path.write_text("nu este json", encoding="utf-8")
            with self.assertRaises(BackupFormatError):
                load_backup(path)
            with self.assertRaises(BackupFormatError):
                parse_backup({"format": "call-book-backup", "version": 99})
            with self.assertRaises(BackupFormatError):
                parse_backup(
                    {
                        "format": "call-book-backup",
                        "version": 1,
                        "qsos": [{"callsign": "", "frequency_mhz": 145.5, "mode": "FM"}],
                    }
                )
            self.assertEqual(target.list_qsos({}), [])

    def test_backup_file_is_readable_json_with_a_dated_default_name(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source_database(directory)
            path = export_backup(source, directory=Path(directory) / "backups")

            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["format"], "call-book-backup")
            self.assertEqual(len(document["qsos"]), 2)
            self.assertEqual(document["operator_profile"]["callsign"], "YO5ABC")
            self.assertRegex(path.name, r"^call_book_backup_\d{8}_\d{6}\.json$")
