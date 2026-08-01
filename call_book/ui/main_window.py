"""Modern PySide6 application shell."""

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import *

from ..application_controller import DuplicateQsoCancelled, LogbookController
from ..config import REFRESH_INTERVAL_OPTIONS, REFRESH_INTERVALS, save_config
from .operator_profile_window import OperatorProfileWindow
from .propagation_panel import PropagationPanel
from .qso_form import QSOForm
from .repeater_window import RepeaterWindow

DARK = (
    'QWidget{background:#171b22;color:#e6edf3;font:10pt "Segoe UI"} '
    "QLineEdit,QTextEdit,QComboBox,QTableWidget{background:#222833;border:1px solid #394454;"
    "border-radius:5px;padding:5px} "
    "QPushButton{background:#2f81f7;border:0;border-radius:5px;padding:7px 12px} "
    "QPushButton:disabled{background:#394454;color:#8b949e} "
    "QGroupBox{border:1px solid #394454;border-radius:7px;margin-top:10px;padding-top:8px;font-weight:bold} "
    "QTabBar::tab{padding:9px 18px;background:#222833} "
    "QHeaderView::section{background:#222833;padding:6px;border:0}"
)


def qso_table_dates(qso_start_utc):
    """Return the local time plus the UTC date and time for a QSO timestamp."""
    utc_datetime = datetime.fromisoformat(qso_start_utc.replace("Z", "+00:00")).astimezone(UTC)
    return (
        utc_datetime.astimezone().strftime("%H:%M:%S"),
        utc_datetime.date().isoformat(),
        utc_datetime.strftime("%H:%M:%S"),
    )


class MainWindow(QMainWindow):
    def __init__(self, db, config):
        super().__init__()
        self.db = db
        self.app_config = config
        self.controller = LogbookController(db)
        self.operator_profile = db.get_operator_profile()
        self.show_propagation_panel = self.app_config.get("show_propagation_panel", "true") == "true"
        self.propagation_panel = None
        self.setWindowTitle("Radio Logbook")
        # Wide enough that the "Benzi și frecvențe" panel's two reference
        # tables fit side by side without a horizontal scrollbar; the panel
        # itself scrolls vertically, so height doesn't need the same care.
        self.resize(1600, 950)
        self.setMinimumSize(1550, 900)
        self.setStyleSheet(DARK)
        self._menu()
        self._build()
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._clock)
        self.clock_timer.start(1000)
        self._clock()
        self.propagation_auto_refresh_timer = QTimer(self)
        self.propagation_auto_refresh_timer.setSingleShot(True)
        self.propagation_auto_refresh_timer.timeout.connect(self._automatic_propagation_refresh)
        self._schedule_propagation_auto_refresh()
        self.weather_auto_refresh_timer = QTimer(self)
        self.weather_auto_refresh_timer.setSingleShot(True)
        self.weather_auto_refresh_timer.timeout.connect(self._automatic_weather_refresh)
        self._schedule_weather_auto_refresh()
        # Deferred, like the propagation panel's own refresh: avoids a network
        # call firing before the window is even shown, and keeps plain
        # widget-construction (including tests) free of background I/O, since
        # a QTimer only fires once the Qt event loop actually runs.
        QTimer.singleShot(1500, self.form.weather_panel.refresh)
        self.refresh()

    def _menu(self):
        file = self.menuBar().addMenu("Fișier")
        for title, fn in [
            ("Exportă Excel", self.excel),
            ("Exportă ADIF", self.adif),
            ("Creează backup", self.backup),
            ("Ieșire", self.close),
        ]:
            action = QAction(title, self)
            action.triggered.connect(fn)
            file.addAction(action)
        settings = self.menuBar().addMenu("Setări")
        settings.addAction("Date operator", self.open_operator_profile)
        settings.addAction("Repetoare", self.open_repeaters)
        settings.addAction("Setări propagare", self.open_propagation_settings)
        settings.addAction("Setări vreme locală", self.open_weather_settings)
        settings.addSeparator()
        settings.addAction("Resetează numerotarea ID-urilor", self.reset_id_sequences)

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("<h2>Radio Logbook</h2>"))
        self.station_locator = QLabel()
        bar.addWidget(self.station_locator)
        self._update_station_locator()
        bar.addStretch()
        self.clock = QLabel()
        bar.addWidget(self.clock)
        root.addLayout(bar)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self.log = QWidget()
        self.location = QWidget()
        self.tabs.addTab(self.log, "Jurnal QSO")
        if self.show_propagation_panel:
            self.propagation_tab = QWidget()
            self.tabs.addTab(self.propagation_tab, "Propagare")
            self._propagation()
        self.tabs.addTab(self.location, "Locație")
        self._log()
        self._location()
        self.status = QLabel("Gata pentru un QSO nou.")
        root.addWidget(self.status)

    def _log(self):
        layout = QVBoxLayout(self.log)
        self.form = QSOForm(
            self.db.list_repeaters, lambda: (self.operator_profile.latitude, self.operator_profile.longitude)
        )
        self.form.contextChanged.connect(self.propagation_context_changed)
        layout.addWidget(self.form)
        actions = QHBoxLayout()
        for name, fn in [
            ("Salvează QSO", self.save),
            ("QSO nou", self.cancel_edit),
            ("Editează", self.edit),
            ("Șterge", self.delete),
        ]:
            b = QPushButton(name)
            b.clicked.connect(fn)
            actions.addWidget(b)
        self.search_button = QPushButton("Căutare")
        self.search_button.setCheckable(True)
        actions.addWidget(self.search_button)
        actions.addStretch()
        layout.addLayout(actions)

        # Hidden until "Căutare" is toggled, instead of always occupying the
        # top of the tab — the filters are used occasionally, not on every view.
        self.filters_container = QWidget()
        self.filters_container.setVisible(False)
        filters = QHBoxLayout(self.filters_container)
        filters.setContentsMargins(0, 0, 0, 0)
        self.filters_edits = {}
        for key, label in [
            ("callsign", "Indicativ"),
            ("band", "Bandă"),
            ("mode", "Mod"),
            ("repeater_id", "Repetor ID"),
            ("date_from", "De la"),
            ("date_to", "Până la"),
        ]:
            e = QLineEdit()
            e.setPlaceholderText(label)
            filters.addWidget(e)
            self.filters_edits[key] = e
        b = QPushButton("Aplică filtre")
        b.clicked.connect(self.refresh)
        filters.addWidget(b)
        layout.addWidget(self.filters_container)
        self.search_button.toggled.connect(self.filters_container.setVisible)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            (
                "ID",
                "Ora locală",
                "Dată UTC",
                "Ora UTC",
                "Indicativ",
                "Nume",
                "Grid Square",
                "MHz",
                "Bandă",
                "Mod",
                "Repetor",
            )
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def _propagation(self):
        layout = QVBoxLayout(self.propagation_tab)
        self.propagation_panel = PropagationPanel()
        layout.addWidget(self.propagation_panel)

    def _location(self):
        layout = QVBoxLayout(self.location)
        p = self.operator_profile
        layout.addWidget(
            QLabel(
                "<h2>Poziția stației</h2>"
                f"<p>Locator: <b>{p.grid_square or p.maidenhead_locator or 'Nesetat'}</b></p>"
                f"<p>Latitudine: {p.latitude or '—'} · Longitudine: {p.longitude or '—'}</p>"
            )
        )
        b = QPushButton("Deschide profilul operatorului")
        b.clicked.connect(self.open_operator_profile)
        layout.addWidget(b)
        layout.addStretch()

    def filters(self):
        return {k: e.text() for k, e in self.filters_edits.items()}

    def refresh(self):
        rows = self.db.list_qsos(self.filters())
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            local_time, utc_date, utc_time = qso_table_dates(r["qso_start_utc"])
            vals = (
                r["id"],
                local_time,
                utc_date,
                utc_time,
                r["callsign"],
                r["operator_name"],
                r["grid_square"],
                r["frequency_mhz"],
                r["band"],
                r["mode"],
                r["repeater_name"] or "",
            )
            for j, v in enumerate(vals):
                self.table.setItem(i, j, QTableWidgetItem(str(v)))
        self.status.setText(f"{len(rows)} QSO-uri afișate.")

    def current_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        id_item = self.table.item(rows[0].row(), 0)
        assert id_item is not None  # refresh() always sets column 0 for every row
        return int(id_item.text())

    def edit(self):
        if (i := self.current_id()) is not None:
            self.form.load(self.db.get_qso(i))
            self.tabs.setCurrentWidget(self.log)

    def cancel_edit(self):
        self.form.new()
        self.table.clearSelection()
        self.status.setText("Gata pentru un QSO nou.")

    def save(self):
        try:
            _, editing = self.controller.save_qso(
                self.form.value(),
                lambda _: (
                    QMessageBox.question(self, "Posibil duplicat", "Există un QSO similar. Salvați?")
                    == QMessageBox.StandardButton.Yes
                ),
            )
            self.refresh()
            self.cancel_edit()
            self.status.setText("QSO actualizat." if editing else "QSO salvat.")
        except DuplicateQsoCancelled:
            pass
        except (ValueError, OSError, KeyError) as e:
            QMessageBox.critical(self, "Eroare", str(e))

    def delete(self):
        if (i := self.current_id()) is not None and QMessageBox.question(
            self, "Confirmare", "Ștergeți QSO-ul?"
        ) == QMessageBox.StandardButton.Yes:
            self.db.delete_qso(i)
            self.refresh()
            self.cancel_edit()

    def propagation_context_changed(self, band, freq):
        if self.propagation_panel is not None:
            self.propagation_panel.schedule(band)

    def _schedule_propagation_auto_refresh(self):
        """Reschedule the recurring background refresh from the current config.

        Re-reads propagation_auto_refresh_minutes each time so a change saved
        in Setări → Setări propagare takes effect on the next cycle.
        """
        self.propagation_auto_refresh_timer.stop()
        if not self.show_propagation_panel:
            return
        try:
            minutes = int(self.app_config.get("propagation_auto_refresh_minutes", "15"))
        except ValueError:
            minutes = 15
        if str(minutes) not in REFRESH_INTERVALS:
            return
        self.propagation_auto_refresh_timer.start(minutes * 60 * 1000)

    def _automatic_propagation_refresh(self):
        if self.propagation_panel is not None and self.form.text("band"):
            self.propagation_context_changed(self.form.text("band"), self.form.text("frequency_mhz"))
        self._schedule_propagation_auto_refresh()

    def _schedule_weather_auto_refresh(self):
        """Reschedule the recurring background refresh from the current config.

        Re-reads local_weather_auto_refresh_minutes each time so a change
        saved in Setări → Setări vreme locală takes effect on the next cycle.
        """
        self.weather_auto_refresh_timer.stop()
        try:
            minutes = int(self.app_config.get("local_weather_auto_refresh_minutes", "30"))
        except ValueError:
            minutes = 30
        automatic_refresh_enabled = str(minutes) in REFRESH_INTERVALS
        self.form.weather_panel.set_manual_refresh_available(not automatic_refresh_enabled)
        if not automatic_refresh_enabled:
            return
        self.weather_auto_refresh_timer.start(minutes * 60 * 1000)

    def _automatic_weather_refresh(self):
        self.form.weather_panel.refresh()
        self._schedule_weather_auto_refresh()

    def _update_station_locator(self):
        locator = self.operator_profile.grid_square or self.operator_profile.maidenhead_locator
        self.station_locator.setText(f"<h2>{locator}</h2>" if locator else "")

    def open_operator_profile(self):
        d = OperatorProfileWindow(self, self.db)
        d.exec()
        self.operator_profile = self.db.get_operator_profile()
        self._update_station_locator()
        self.form.weather_panel.refresh()

    def open_repeaters(self):
        d = RepeaterWindow(self, self.db, self.form.refresh_repeaters)
        d.exec()

    def open_propagation_settings(self):
        d = QDialog(self)
        layout = QFormLayout(d)
        enabled = QCheckBox("Actualizare automată")
        interval = QComboBox()
        interval.addItems(REFRESH_INTERVAL_OPTIONS)
        current = self.app_config.get("propagation_auto_refresh_minutes", "15")
        enabled.setChecked(current in REFRESH_INTERVALS)
        if current in REFRESH_INTERVALS:
            interval.setCurrentText(current)
        layout.addRow(enabled)
        layout.addRow("Interval (minute)", interval)
        b = QPushButton("Salvează")

        def save_and_close():
            self.app_config["propagation_auto_refresh_minutes"] = interval.currentText() if enabled.isChecked() else "0"
            save_config(self.app_config)
            self._schedule_propagation_auto_refresh()
            d.accept()

        b.clicked.connect(save_and_close)
        layout.addRow(b)
        d.exec()

    def open_weather_settings(self):
        d = QDialog(self)
        layout = QFormLayout(d)
        enabled = QCheckBox("Actualizare automată")
        interval = QComboBox()
        interval.addItems(REFRESH_INTERVAL_OPTIONS)
        current = self.app_config.get("local_weather_auto_refresh_minutes", "30")
        enabled.setChecked(current in REFRESH_INTERVALS)
        if current in REFRESH_INTERVALS:
            interval.setCurrentText(current)
        layout.addRow(enabled)
        layout.addRow("Interval (minute)", interval)
        b = QPushButton("Salvează")

        def save_and_close():
            self.app_config["local_weather_auto_refresh_minutes"] = (
                interval.currentText() if enabled.isChecked() else "0"
            )
            save_config(self.app_config)
            self._schedule_weather_auto_refresh()
            d.accept()

        b.clicked.connect(save_and_close)
        layout.addRow(b)
        d.exec()

    def _export(self, title, extension, exporter):
        name, _ = QFileDialog.getSaveFileName(self, f"Export {title}", "exports", f"{title} (*{extension})")
        if name:
            try:
                self.status.setText(f"Export creat: {exporter(self.controller.list_qsos(self.filters()), Path(name))}")
            except Exception as e:
                QMessageBox.critical(self, "Eroare export", str(e))

    def excel(self):
        self._export("Excel", ".xlsx", self.controller.export_excel)

    def adif(self):
        self._export("ADIF", ".adi", self.controller.export_adif)

    def backup(self):
        try:
            self.status.setText(f"Backup creat: {self.controller.create_backup()}")
        except Exception as e:
            QMessageBox.critical(self, "Eroare backup", str(e))

    def reset_id_sequences(self):
        message = (
            "Resetați numerotarea ID-urilor pentru QSO-uri, repetoare și stații?\n\n"
            "Datele existente nu vor fi șterse. Următorul ID va urma cel mai mare ID existent."
        )
        if QMessageBox.question(self, "Confirmare resetare ID-uri", message) == QMessageBox.StandardButton.Yes:
            try:
                self.db.reset_id_sequences()
                self.status.setText("Numerotarea ID-urilor a fost resetată.")
            except OSError as e:
                QMessageBox.critical(self, "Eroare", str(e))

    def _clock(self):
        self.clock.setText(f"Local {datetime.now():%H:%M:%S}  |  UTC {datetime.now(UTC):%H:%M:%S}")

    def closeEvent(self, event):
        self.propagation_auto_refresh_timer.stop()
        self.weather_auto_refresh_timer.stop()
        if self.propagation_panel is not None:
            self.propagation_panel.shutdown()
        self.form.shutdown()
        event.accept()
