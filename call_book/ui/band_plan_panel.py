"""Static reference panel: exact ANCOM amateur band segments and which of them are shared with government use."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.band_plan import AMATEUR_SEGMENTS, SHARED_SEGMENTS

_CELL_PADDING = 40
_ROW_PADDING = 10
_SCROLL_AREA_HEIGHT = 380


def _shared_codes(allocation_status):
    # e.g. "G(A)/G/NG" -> "G(A), G": the non-amateur codes sharing this segment.
    return ", ".join(code for code in allocation_status.split("/") if code != "NG")


def _sized_table(rows):
    """Build a table sized to show every row/column with no internal scrollbars.

    A plain QTableWidget doesn't factor its actual row/column sizes into its
    sizeHint, so without this it gets squeezed down to a default size,
    truncating the reference data. Column/row sizes are measured directly
    with QFontMetrics rather than via resizeColumnsToContents()/columnWidth(),
    which report sizes that are too tight (or not yet settled) before the
    widget has actually been laid out and shown. The table can still be
    taller than the panel's visible area — see the enclosing QScrollArea.
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
    """Exact ANCOM amateur band segments (160m–70cm) and which are shared with government use.

    Static data (see ``services.band_plan``), not a live/fetched table. Both
    tables are sized to show every row without their own scrollbars, but
    together they're taller than most screens allow even maximized — so the
    pair sits inside a vertically scrollable area instead of forcing the
    whole window to grow to fit them.
    """

    def __init__(self, parent=None):
        super().__init__("Benzi și frecvențe (referință)", parent)
        layout = QVBoxLayout(self)

        disclaimer = QLabel(
            "Date ANCOM (160m–70cm); verifică reglementarea curentă. Codurile G/G(A) sunt cele din sursă — "
            "vezi reglementarea ANCOM pentru semnificația exactă. Notele *, **, (1)(2)(3) provin din sursă și "
            "nu sunt reproduse aici."
        )
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        tables_widget = QWidget()
        tables = QHBoxLayout(tables_widget)

        amateur_box = QGroupBox("Radioamator — toate segmentele")
        amateur_layout = QVBoxLayout(amateur_box)
        self.amateur_table = _sized_table(
            [{"Bandă": e.band, "Frecvență": e.frequency_range, "Statut bandă": e.band_status} for e in AMATEUR_SEGMENTS]
        )
        amateur_layout.addWidget(self.amateur_table)
        tables.addWidget(amateur_box)

        shared_box = QGroupBox("Segmente partajate cu utilizare guvernamentală")
        shared_layout = QVBoxLayout(shared_box)
        self.shared_table = _sized_table(
            [
                {
                    "Bandă": e.band,
                    "Frecvență": e.frequency_range,
                    "Partajat cu": _shared_codes(e.allocation_status),
                    "Statut bandă": e.band_status,
                }
                for e in SHARED_SEGMENTS
            ]
        )
        shared_layout.addWidget(self.shared_table)
        tables.addWidget(shared_box)

        scroll = QScrollArea()
        scroll.setWidget(tables_widget)
        scroll.setWidgetResizable(False)
        scroll.setFixedHeight(_SCROLL_AREA_HEIGHT)
        layout.addWidget(scroll)
