"""Reference panel: the ANCOM amateur band segments, searchable and filterable.

One table, not two. The previous layout showed all segments beside a second
table listing the shared ones — a strict subset, so every shared segment was
printed twice — and both were sized in fixed pixels inside a fixed-height
scroll area, which is what made the window demand ~1550px of width. Here the
sharing status is a column and a colour, the table resizes with the panel,
and the filters do what the second table used to.
"""

from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..services.band_plan import AMATEUR_SEGMENTS, band_labels

COLUMNS = ("Bandă", "Interval", "Statut", "Partajat cu")
ALL_BANDS = "Toate benzile"

# Tints that stay readable on the application's dark palette.
_SHARED_BACKGROUND = QColor("#3a2f1c")
_SHARED_FOREGROUND = QColor("#e3b341")
_MATCH_BACKGROUND = QColor("#123a5e")
_MATCH_FOREGROUND = QColor("#79c0ff")
_EXCLUSIVE_FOREGROUND = QColor("#7ee787")

_DISCLAIMER = (
    "Date ANCOM (160m–70cm), reproduse ca referință rapidă — verifică reglementarea în vigoare. "
    "Codurile G/G(A) și notele *, **, (1)(2)(3) sunt cele din sursă."
)


class BandPlanPanel(QGroupBox):
    """Searchable ANCOM band plan, with the segment in use highlighted.

    ``highlight_frequency`` is what ties it to the QSO form: typing a
    frequency marks the segment that contains it, so the operator sees the
    allocation status of the exact spot they are working without reading the
    whole table.
    """

    def __init__(self, parent=None):
        super().__init__("Benzi și frecvențe (referință ANCOM)", parent)
        self.segments = AMATEUR_SEGMENTS
        self.highlighted_frequency: float | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Caută bandă sau frecvență…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filters)
        filters.addWidget(self.search, 1)

        self.band_filter = QComboBox()
        self.band_filter.addItem(ALL_BANDS)
        self.band_filter.addItems(band_labels())
        self.band_filter.currentTextChanged.connect(self._apply_filters)
        filters.addWidget(self.band_filter)

        self.shared_only = QCheckBox("Doar partajate")
        self.shared_only.setToolTip("Arată doar segmentele folosite în comun cu servicii guvernamentale.")
        self.shared_only.toggled.connect(self._apply_filters)
        filters.addWidget(self.shared_only)
        layout.addLayout(filters)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        # The interval column takes the slack so the table follows the panel's
        # width instead of the panel having to be wide enough for the table.
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # Enough rows to be worth reading once the panel drops to its own row
        # on a narrower window; it still grows with the space available.
        self.table.setMinimumHeight(150)
        layout.addWidget(self.table, 1)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        disclaimer = QLabel(_DISCLAIMER)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("color:#8b949e")
        layout.addWidget(disclaimer)

        self._apply_filters()

    def visible_segments(self):
        """Return the segments passing the current filters, in table order."""
        text = self.search.text().strip().lower()
        band = self.band_filter.currentText()
        return [
            segment
            for segment in self.segments
            if (not self.shared_only.isChecked() or segment.is_shared_with_government)
            and (band == ALL_BANDS or segment.band_label == band)
            and (
                not text
                or text in segment.band.lower()
                or text in segment.frequency_range.lower()
                or text in segment.band_status.lower()
                or text in segment.allocation_status.lower()
            )
        ]

    def highlight_frequency(self, frequency_mhz):
        """Mark the segment containing ``frequency_mhz``; pass ``None`` to clear."""
        try:
            value = None if frequency_mhz in (None, "") else float(frequency_mhz)
        except (TypeError, ValueError):
            value = None
        if value == self.highlighted_frequency:
            return
        self.highlighted_frequency = value
        self._apply_filters()

    def _apply_filters(self, *_):
        segments = self.visible_segments()
        self.table.setRowCount(len(segments))
        matched_row = None
        for row, segment in enumerate(segments):
            is_match = self.highlighted_frequency is not None and segment.contains(self.highlighted_frequency)
            matched_row = row if is_match and matched_row is None else matched_row
            values = (
                segment.band,
                segment.frequency_range,
                segment.band_status,
                segment.shared_with or "exclusiv radioamatori",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if is_match:
                    item.setBackground(QBrush(_MATCH_BACKGROUND))
                    item.setForeground(QBrush(_MATCH_FOREGROUND))
                elif column == 3:
                    item.setForeground(
                        QBrush(_SHARED_FOREGROUND if segment.is_shared_with_government else _EXCLUSIVE_FOREGROUND)
                    )
                if segment.is_shared_with_government and not is_match and column == 3:
                    item.setBackground(QBrush(_SHARED_BACKGROUND))
                self.table.setItem(row, column, item)
        matched_item = None if matched_row is None else self.table.item(matched_row, 0)
        if matched_item is not None:
            self.table.scrollToItem(matched_item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self._update_summary(segments, matched_row)

    def _update_summary(self, segments, matched_row):
        shared = sum(1 for segment in segments if segment.is_shared_with_government)
        parts = [f"{len(segments)} segmente afișate din {len(self.segments)}", f"{shared} partajate"]
        if self.highlighted_frequency is not None:
            if matched_row is None:
                parts.append(f"<b>{self.highlighted_frequency:g} MHz nu este într-un segment listat</b>")
            else:
                segment = self.visible_segments()[matched_row]
                status = segment.shared_with or "exclusiv radioamatori"
                parts.append(
                    f"<b>{self.highlighted_frequency:g} MHz</b> → {segment.band} "
                    f"{segment.frequency_range} · {segment.band_status} · {status}"
                )
        self.summary.setText(" · ".join(parts))

    def minimumSizeHint(self):
        """Keep the panel from dictating a wide window; it scrolls instead."""
        hint = super().minimumSizeHint()
        hint.setWidth(min(hint.width(), 320))
        return hint

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(max(420, min(hint.width(), 560)))
        return hint
