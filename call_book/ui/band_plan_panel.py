"""Static reference panel: amateur band plan and shared/governmental allocations."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..services.band_plan import AMATEUR_BANDS, SHARED_ALLOCATIONS

_CELL_PADDING = 40
_ROW_PADDING = 10


def _sized_table(rows):
    """Build a table sized to show every row/column without scrollbars.

    A plain QTableWidget doesn't factor its actual row/column sizes into its
    sizeHint, so without this the surrounding layout squeezes it down to a
    default size and both scrollbars appear, truncating the reference data.
    Column/row sizes are measured directly with QFontMetrics rather than via
    resizeColumnsToContents()/columnWidth(), which report sizes that are too
    tight (or not yet settled) before the widget has actually been laid out
    and shown.
    """
    headers = list(rows[0].keys())
    table = QTableWidget(len(rows), len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    for row, values in enumerate(rows):
        for col, value in enumerate(values.values()):
            table.setItem(row, col, QTableWidgetItem(value))

    metrics = QFontMetrics(table.font())
    header_metrics = QFontMetrics(table.horizontalHeader().font())
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    column_widths = []
    for col, header_text in enumerate(headers):
        widest_cell = max((metrics.horizontalAdvance(entry[header_text]) for entry in rows), default=0)
        column_width = max(widest_cell, header_metrics.horizontalAdvance(header_text)) + _CELL_PADDING
        table.setColumnWidth(col, column_width)
        column_widths.append(column_width)

    row_height = metrics.height() + _ROW_PADDING
    for row in range(table.rowCount()):
        table.setRowHeight(row, row_height)

    width = sum(column_widths) + 2 * table.frameWidth() + 4
    height = header.sizeHint().height() + row_height * table.rowCount() + 2 * table.frameWidth() + 4
    table.setFixedSize(width, height)
    return table


class BandPlanPanel(QGroupBox):
    """Quick reference for 160m–70cm: amateur band edges plus shared-use notes.

    Static data (see ``services.band_plan``), not a live/fetched table. Every
    row is sized to fit without scrollbars, so the panel needs a generous
    amount of space — see MainWindow's default/minimum size.
    """

    def __init__(self, parent=None):
        super().__init__("Benzi și frecvențe (referință)", parent)
        layout = QVBoxLayout(self)

        disclaimer = QLabel("Referință generală IARU Regiunea 1 (160m–70cm); verifică reglementarea ANCOM curentă.")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        tables = QHBoxLayout()
        layout.addLayout(tables)

        amateur_box = QGroupBox("Radioamator (NG)")
        amateur_layout = QVBoxLayout(amateur_box)
        self.amateur_table = _sized_table(
            [{"Bandă": e.band, "Frecvență": e.frequency_range, "Note": e.notes} for e in AMATEUR_BANDS]
        )
        amateur_layout.addWidget(self.amateur_table)
        tables.addWidget(amateur_box)

        shared_box = QGroupBox("Alocare partajată / guvernamentală (informativ)")
        shared_layout = QVBoxLayout(shared_box)
        self.shared_table = _sized_table(
            [{"Bandă": e.band, "Serviciu partajat/primar": e.primary_or_shared_service} for e in SHARED_ALLOCATIONS]
        )
        shared_layout.addWidget(self.shared_table)
        tables.addWidget(shared_box)
