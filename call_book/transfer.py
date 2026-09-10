"""Portable full-logbook backups, for moving data between devices.

The `.db` copies produced by :mod:`call_book.backup` are snapshots of one
machine's database and replace everything when restored.  A transfer backup is
a plain JSON document instead: it can be read on any device and is imported by
*merging* into the logbook already there, so a logbook kept on a second device
can be brought home without losing what was logged in the meantime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .database import Database
from .models import QSO, OperatorProfile, Repeater
from .validators import validate_qso

BACKUP_FORMAT = "call-book-backup"
BACKUP_VERSION = 1
_QSO_FIELDS = tuple(field.name for field in fields(QSO) if field.name != "id")
_REPEATER_FIELDS = tuple(field.name for field in fields(Repeater) if field.name != "id")
_PROFILE_FIELDS = tuple(field.name for field in fields(OperatorProfile))


class BackupFormatError(ValueError):
    """The selected file is not a usable Radio Logbook transfer backup."""


@dataclass(frozen=True, slots=True)
class LogbookBackup:
    """Everything a transfer backup carries, already parsed and validated."""

    exported_at: str = ""
    profile: OperatorProfile | None = None
    # Repeaters keep the id they had on the source device only so the QSOs in
    # the same file can point at them; the id itself is never imported.
    repeaters: tuple[tuple[int | None, Repeater], ...] = ()
    # Each QSO travels with its own ``qso_start_utc``, which is not part of the
    # QSO model but is what the logbook sorts and filters on.
    qsos: tuple[tuple[QSO, str], ...] = ()

    @property
    def exported_at_label(self) -> str:
        """The export moment in local time, or a placeholder when unusable."""
        try:
            return datetime.fromisoformat(self.exported_at).astimezone().strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return "dată necunoscută"


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """What an import actually changed in the receiving logbook."""

    imported_qsos: int = 0
    skipped_qsos: int = 0
    imported_repeaters: int = 0
    matched_repeaters: int = 0
    imported_profile: bool = False


def describe_import(summary: ImportSummary) -> str:
    """Human-readable Romanian report shown after an import."""
    return "\n".join(
        (
            f"QSO-uri importate: {summary.imported_qsos}",
            f"QSO-uri deja existente (ignorate): {summary.skipped_qsos}",
            f"Repetoare importate: {summary.imported_repeaters}",
            f"Repetoare deja existente (refolosite): {summary.matched_repeaters}",
            (
                "Profilul operatorului a fost importat (jurnalul curent nu avea unul)."
                if summary.imported_profile
                else "Profilul operatorului din jurnalul curent a fost păstrat."
            ),
        )
    )


def default_backup_name(moment: datetime | None = None) -> str:
    return f"call_book_backup_{(moment or datetime.now()).strftime('%Y%m%d_%H%M%S')}.json"


def build_backup_document(database: Database) -> dict[str, Any]:
    """Serialize the whole logbook into a device-independent JSON document."""
    profile = database.get_operator_profile()
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "operator_profile": {name: getattr(profile, name) for name in _PROFILE_FIELDS},
        "repeaters": [
            {"id": row["id"], **{name: row[name] for name in _REPEATER_FIELDS}} for row in database.list_repeaters()
        ],
        "qsos": [
            {"qso_start_utc": row["qso_start_utc"], **{name: row[name] for name in _QSO_FIELDS}}
            for row in database.list_qsos({})
        ],
    }


def export_backup(database: Database, directory: Path = Path("backups"), destination: Path | None = None) -> Path:
    path = destination or directory / default_backup_name()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_backup_document(database), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_backup(path: Path) -> LogbookBackup:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise BackupFormatError("Fișierul nu este un backup Radio Logbook (nu este text UTF-8).") from exc
    except json.JSONDecodeError as exc:
        raise BackupFormatError("Fișierul nu este un backup Radio Logbook (JSON invalid).") from exc
    return parse_backup(document)


def parse_backup(document: Any) -> LogbookBackup:
    if not isinstance(document, dict) or document.get("format") != BACKUP_FORMAT:
        raise BackupFormatError("Fișierul nu este un backup Radio Logbook.")
    version = document.get("version")
    if not isinstance(version, int) or version > BACKUP_VERSION:
        raise BackupFormatError(f"Versiune de backup neacceptată ({version}). Actualizați aplicația.")
    return LogbookBackup(
        exported_at=_text(document.get("exported_at")),
        profile=_parse_profile(document.get("operator_profile")),
        repeaters=tuple(_parse_repeater(item) for item in _entries(document, "repeaters")),
        qsos=tuple(_parse_qso(item) for item in _entries(document, "qsos")),
    )


def import_backup(database: Database, backup: LogbookBackup, *, overwrite_profile: bool = False) -> ImportSummary:
    """Merge a parsed backup into ``database`` without touching existing records.

    Ids are device-local, so repeaters are matched by name and output frequency
    and QSOs by callsign, frequency, mode and their original timestamp; anything
    already present is left exactly as it is.
    """
    repeater_ids: dict[int, int] = {}
    imported_repeaters = matched_repeaters = 0
    for source_id, repeater in backup.repeaters:
        existing = database.find_repeater_id(repeater.name, repeater.output_frequency_mhz)
        if existing is None:
            existing = database.save_repeater(replace(repeater, id=None))
            imported_repeaters += 1
        else:
            matched_repeaters += 1
        if source_id is not None:
            repeater_ids[source_id] = existing

    imported_qsos = skipped_qsos = 0
    for source_qso, qso_start_utc in backup.qsos:
        source_repeater_id = source_qso.repeater_id
        qso = replace(
            source_qso,
            id=None,
            # A QSO whose repeater is missing from the file keeps the QSO but
            # loses the link, exactly like deleting a repeater does locally.
            repeater_id=repeater_ids.get(source_repeater_id) if source_repeater_id is not None else None,
        )
        if database.qso_exists(qso.callsign, qso.frequency_mhz, qso.mode, qso_start_utc):
            skipped_qsos += 1
            continue
        database.import_qso(qso, qso_start_utc)
        imported_qsos += 1

    # The receiving device keeps its own operator profile unless it has none:
    # importing a logbook must not silently rewrite who this station is.
    imported_profile = False
    if backup.profile is not None and (overwrite_profile or _profile_is_blank(database.get_operator_profile())):
        database.save_operator_profile(backup.profile)
        imported_profile = True
    return ImportSummary(
        imported_qsos=imported_qsos,
        skipped_qsos=skipped_qsos,
        imported_repeaters=imported_repeaters,
        matched_repeaters=matched_repeaters,
        imported_profile=imported_profile,
    )


def _entries(document: dict[str, Any], key: str) -> list[Any]:
    value = document.get(key, [])
    if not isinstance(value, list):
        raise BackupFormatError(f"Secțiunea „{key}” din backup este coruptă.")
    return value


def _parse_repeater(item: Any) -> tuple[int | None, Repeater]:
    if not isinstance(item, dict):
        raise BackupFormatError("Un repetor din backup este corupt.")
    name = _text(item.get("name"))
    if not name:
        raise BackupFormatError("Un repetor din backup nu are nume.")
    output = _optional_float(item.get("output_frequency_mhz"))
    if output is None or output <= 0:
        raise BackupFormatError(f"Repetorul „{name}” are o frecvență de ieșire invalidă.")
    return _optional_int(item.get("id")), Repeater(
        name=name,
        output_frequency_mhz=output,
        input_frequency_mhz=_optional_float(item.get("input_frequency_mhz")),
        shift_mhz=_optional_float(item.get("shift_mhz")),
        tone_hz=_optional_float(item.get("tone_hz")),
        mode=_text(item.get("mode")),
        location=_text(item.get("location")),
        grid_square=_text(item.get("grid_square")),
        notes=_text(item.get("notes")),
    )


def _parse_qso(item: Any) -> tuple[QSO, str]:
    if not isinstance(item, dict):
        raise BackupFormatError("Un QSO din backup este corupt.")
    callsign = _text(item.get("callsign"))
    frequency = _optional_float(item.get("frequency_mhz"))
    if frequency is None:
        raise BackupFormatError(f"QSO-ul „{callsign or '?'}” din backup are o frecvență invalidă.")
    # created_at and qso_start_utc are NOT NULL in the schema; a backup written
    # by an older or hand-edited file may miss one, so each falls back to the
    # other and, in the worst case, to the moment of the import.
    created_at = _text(item.get("created_at"))
    qso_start_utc = _text(item.get("qso_start_utc")) or created_at or datetime.now(UTC).isoformat()
    qso = QSO(
        callsign=callsign,
        frequency_mhz=frequency,
        mode=_text(item.get("mode")),
        band=_text(item.get("band")),
        repeater_id=_optional_int(item.get("repeater_id")),
        operator_name=_text(item.get("operator_name")),
        grid_square=_text(item.get("grid_square")),
        notes=_text(item.get("notes")),
        created_at=created_at or qso_start_utc,
        updated_at=_text(item.get("updated_at")) or None,
        my_grid_square=_text(item.get("my_grid_square")),
        propagation_mode=_text(item.get("propagation_mode")) or "Necunoscută",
        propagation_notes=_text(item.get("propagation_notes")),
    )
    try:
        validate_qso(qso)
    except ValueError as exc:
        raise BackupFormatError(f"QSO invalid în backup („{callsign or '?'}”): {exc}") from exc
    return qso, qso_start_utc


def _parse_profile(item: Any) -> OperatorProfile | None:
    if not isinstance(item, dict):
        return None
    numeric = {"default_power_w", "latitude", "longitude", "location_accuracy_m"}
    values: dict[str, Any] = {
        name: _optional_float(item.get(name)) if name in numeric else _text(item.get(name)) for name in _PROFILE_FIELDS
    }
    return OperatorProfile(**values)


def _profile_is_blank(profile: OperatorProfile) -> bool:
    """A profile counts as unset while it identifies no operator."""
    return not (_text(profile.callsign) or _text(profile.full_name))


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
