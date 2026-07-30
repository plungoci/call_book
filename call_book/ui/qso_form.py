"""Qt QSO editor; presentation only, with domain validation kept in controllers."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from ..models import QSO
from ..propagation import PROPAGATION_MODES
from ..services.band_detector import BandDetector
from ..services.propagation_service import (
    PROPAGATION_UNKNOWN,
    PropagationSuggestionState,
    suggest_propagation_mode,
)
from ..utils.text_formatters import format_callsign, format_grid_square, format_operator_name
from .local_weather_panel import LocalWeatherPanel

# Field values (callsigns, frequencies, band/mode names) are all short; a
# fixed cap keeps the inputs a sensible size instead of stretching them to
# fill the whole window width, leaving room for the weather panel beside them.
_FIELD_MAX_WIDTH = 220

MODES = (
    "FM",
    "AM",
    "SSB",
    "USB",
    "LSB",
    "CW",
    "RTTY",
    "FT8",
    "FT4",
    "PSK31",
    "DIGITAL",
    "MSK144",
    "EchoLink",
    "AllStar",
    "DMR",
    "D-STAR",
    "C4FM",
    "Internet Gateway",
)

# The field name is deliberately the same as the QSO model attribute.  Keep this
# single source of truth in sync whenever a form field is added or renamed.
FORM_FIELDS = (
    ("Indicativ", "callsign"),
    ("Nume", "operator_name"),
    ("Repetor", "repeater"),
    ("Frecvență MHz", "frequency_mhz"),
    ("Bandă", "band"),
    ("Mod", "mode"),
    ("Locator", "grid_square"),
    ("Propagare", "propagation_mode"),
)
LABELS = {key: label for label, key in FORM_FIELDS}

FIELD_GROUPS = (
    (
        "Legătură",
        (
            "callsign",
            "operator_name",
            "grid_square",
            "frequency_mhz",
            "band",
            "mode",
            "repeater",
            "propagation_mode",
        ),
    ),
)
FIELD_KEYS = tuple(key for _, keys in FIELD_GROUPS for key in keys)
COMBO_BOX_FIELDS = {"repeater", "mode", "propagation_mode"}


def validate_field_labels() -> None:
    """Fail early when form definitions and their user-facing labels diverge."""
    duplicate_keys = {key for key in FIELD_KEYS if FIELD_KEYS.count(key) > 1}
    missing_labels = [key for key in FIELD_KEYS if key not in LABELS]
    unused_labels = sorted(set(LABELS) - set(FIELD_KEYS))
    if duplicate_keys:
        raise ValueError(f"Câmpuri QSO duplicate: {', '.join(sorted(duplicate_keys))}")
    if missing_labels:
        raise ValueError(f"Lipsesc etichete pentru câmpurile: {', '.join(missing_labels)}")
    if unused_labels:
        raise ValueError(f"Etichete fără câmp asociat: {', '.join(unused_labels)}")


class QSOForm(QGroupBox):
    contextChanged = Signal(str, str)

    def __init__(self, repeaters, location_provider=None):
        super().__init__("QSO · toate orele sunt UTC")
        self.repeaters = repeaters
        self.location_provider = location_provider or (lambda: (None, None))
        self.qso_id = None
        self.fields = {}
        self._loading = False
        self.propagation_state = PropagationSuggestionState()
        self._applying_suggestion = False

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        layout.addLayout(grid)
        for column, (title, keys) in enumerate(FIELD_GROUPS):
            box = QGroupBox(title)
            form = QFormLayout(box)
            grid.addWidget(box, 0, column, 1, len(FIELD_GROUPS))
            for key in keys:
                widget = self._create_widget(key)
                # A missing translation must not prevent the logbook from
                # opening.  The explicit validator remains available to tests
                # and development checks, while this fallback keeps the UI
                # usable with a readable generated label.
                label_text = LABELS.get(key, key.replace("_", " ").title())
                widget.setToolTip(self._tooltip(key, label_text))
                form.addRow(label_text, widget)
                self.fields[key] = widget
        self.weather_panel = LocalWeatherPanel(self.location_provider)
        grid.addWidget(self.weather_panel, 0, len(FIELD_GROUPS))
        grid.setColumnStretch(len(FIELD_GROUPS), 1)

        self.notes = QTextEdit()
        self.notes.setFixedHeight(72)
        self.notes.setToolTip("Informații suplimentare despre QSO.")
        layout.addWidget(self.notes)

        self._line("callsign").textEdited.connect(
            lambda text: self._format_live_input("callsign", format_callsign, text)
        )
        self._line("grid_square").textEdited.connect(
            lambda text: self._format_live_input("grid_square", format_grid_square, text)
        )
        self._line("operator_name").textEdited.connect(
            lambda text: self._format_live_input("operator_name", format_operator_name, text)
        )
        self._line("frequency_mhz").textChanged.connect(self._frequency_changed)
        self._line("band").textChanged.connect(self._context)
        self._line("band").textChanged.connect(self._update_propagation_suggestion)
        self.fields["mode"].currentTextChanged.connect(self._update_propagation_suggestion)
        self.fields["repeater"].currentTextChanged.connect(self._update_propagation_suggestion)
        self.fields["propagation_mode"].currentTextChanged.connect(self._propagation_mode_changed)
        # Populate the editable combobox during form construction as well as
        # after repeater management changes.  Previously it was refreshed only
        # after closing the management dialog, so repeaters already stored in
        # the database were absent when the application first opened.
        self.refresh_repeaters()
        self.new()

    def _create_widget(self, key):
        widget = QComboBox() if key in COMBO_BOX_FIELDS else QLineEdit()
        widget.setMaximumWidth(_FIELD_MAX_WIDTH)
        if not isinstance(widget, QComboBox):
            return widget

        # All combo fields (repeater, mode, propagation_mode) are plain,
        # non-editable dropdowns: click anywhere to open the list, pick a
        # value, it closes. Keeping them all non-editable is what makes
        # Repeater behave identically to Mode/Propagation mode.
        widget.addItems(
            {
                "mode": MODES,
                "propagation_mode": PROPAGATION_MODES,
            }.get(key, [])
        )
        if key == "repeater":
            widget.currentTextChanged.connect(self._repeater)
        return widget

    @staticmethod
    def _tooltip(key, label_text):
        if key == "callsign":
            return "Introdu indicativul stației corespondente. Literele sunt transformate automat în majuscule."
        if key == "grid_square":
            return "Introdu locatorul Maidenhead. Literele sunt transformate automat în majuscule."
        return f"Valoarea {label_text.lower()} pentru acest QSO."

    def _line(self, key):
        return self.fields[key]

    def text(self, key):
        widget = self.fields[key]
        return widget.currentText() if isinstance(widget, QComboBox) else widget.text()

    def set_text(self, key, value):
        widget = self.fields[key]
        if isinstance(widget, QComboBox):
            widget.setCurrentText(str(value))
        else:
            formatter = format_grid_square if key == "grid_square" else str
            widget.setText(formatter(str(value)))

    def _format_live_input(self, key, formatter, value):
        """Format a user edit without moving the insertion cursor.

        ``textEdited`` is emitted only for user edits, so calling ``setText`` here
        cannot recursively re-enter this handler for programmatic form loading.
        """
        formatted = formatter(value)
        if formatted == value:
            return
        line = self._line(key)
        cursor_position = line.cursorPosition()
        line.setText(formatted)
        line.setCursorPosition(min(cursor_position, len(formatted)))

    def _frequency_changed(self, value):
        if self._loading:
            return
        try:
            band = BandDetector.frequency_to_band(float(value))
        except ValueError:
            return
        if band:
            self.set_text("band", band)
        self._context()

    def _context(self, *_):
        if not self._loading:
            self.contextChanged.emit(self.text("band"), self.text("frequency_mhz"))

    def _repeater(self, text):
        if self._loading or not text:
            return
        repeater_id = text.split(" ")[0]
        repeater = next((item for item in self.repeaters() if str(item["id"]) == repeater_id), None)
        if repeater:
            self.set_text("frequency_mhz", repeater["output_frequency_mhz"])
            self.set_text("mode", repeater["mode"] or "FM")

    def _update_propagation_suggestion(self, *_):
        if self._loading:
            return
        suggestion = suggest_propagation_mode(
            self.text("band"),
            mode=self.text("mode"),
            repeater_selected=bool(self.text("repeater").strip()),
        )
        if self.propagation_state.may_apply(suggestion):
            self._applying_suggestion = True
            self.set_text("propagation_mode", suggestion)
            self._applying_suggestion = False

    def _propagation_mode_changed(self, *_):
        if self._loading or self._applying_suggestion:
            return
        self.propagation_state.mark_manual()

    def refresh_repeaters(self):
        widget = self.fields["repeater"]
        current = widget.currentText()
        widget.blockSignals(True)
        widget.clear()
        widget.addItem("")
        widget.addItems([f"{item['id']} — {item['name']}" for item in self.repeaters()])
        widget.setCurrentText(current)
        widget.blockSignals(False)

    def new(self):
        # Keep the propagation mode from the previous QSO.  Operators commonly
        # log several consecutive contacts using the same propagation path.
        previous_propagation_mode = self.text("propagation_mode") or PROPAGATION_UNKNOWN
        self._loading = True
        self.qso_id = None
        for key in self.fields:
            self.set_text(key, "")
        self.set_text("mode", "FM")
        self.set_text("propagation_mode", previous_propagation_mode)
        self.notes.clear()
        self.propagation_state.reset_for_new_qso()
        self._loading = False
        self.fields["callsign"].setFocus()

    def load(self, qso):
        self._loading = True
        self.qso_id = qso.id
        for key in self.fields:
            if key == "repeater":
                self.set_text(key, f"{qso.repeater_id} —" if qso.repeater_id else "")
            elif hasattr(qso, key):
                self.set_text(key, getattr(qso, key) or "")
        self.notes.setPlainText(qso.notes)
        self.propagation_state.load_existing_qso()
        self._loading = False

    def value(self):
        repeater_id = self.text("repeater").split(" ")[0]
        text = self.text
        return QSO(
            id=self.qso_id,
            callsign=text("callsign"),
            operator_name=text("operator_name"),
            repeater_id=int(repeater_id) if repeater_id.isdigit() else None,
            frequency_mhz=float(text("frequency_mhz")),
            band=text("band"),
            mode=text("mode"),
            grid_square=text("grid_square").upper(),
            notes=self.notes.toPlainText(),
            propagation_mode=text("propagation_mode"),
        )

    def shutdown(self):
        self.weather_panel.shutdown()
