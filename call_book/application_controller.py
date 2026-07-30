"""Application use-cases independent from Qt widgets and dialogs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .adif_export import export_adif
from .backup import create_backup
from .database import Database
from .excel_export import export_excel
from .models import QSO
from .validators import validate_qso


class LogbookController:
    """Coordinates persistence and file operations while UI owns presentation."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def save_qso(self, qso: QSO, confirm_duplicate: Callable[[QSO], bool]) -> tuple[int, bool]:
        is_edit = qso.id is not None
        if not is_edit:
            qso.my_grid_square = self.database.get_operator_profile().grid_square
        validate_qso(qso)
        if self.database.possible_duplicate(qso) and not confirm_duplicate(qso):
            raise DuplicateQsoCancelled()
        return self.database.save_qso(qso), is_edit

    def list_qsos(self, filters: dict[str, str]) -> list[QSO]:
        return [QSO.from_row(row) for row in self.database.list_qsos(filters)]

    def export_excel(self, qsos: list[QSO], destination: Path) -> Path:
        return export_excel(qsos, destination=destination)

    def export_adif(self, qsos: list[QSO], destination: Path) -> Path:
        return export_adif(qsos, destination=destination, profile=self.database.get_operator_profile())

    def create_backup(self) -> Path:
        return create_backup(self.database.path)


class DuplicateQsoCancelled(Exception):
    """The user declined saving a detected duplicate QSO."""
