"""Thread-safe Qt propagation dashboard."""

from datetime import UTC, datetime

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..services.propagation_estimator import PropagationEstimator
from ..services.space_weather_service import SpaceWeatherService
from ..validators import frequency_range_for_band


class Worker(QObject):
    finished = Signal(object)
    failed = Signal()

    def __init__(self, force):
        super().__init__()
        self.force = force

    def run(self):
        try:
            self.finished.emit(SpaceWeatherService().fetch(self.force))
        except Exception:
            self.failed.emit()


class PropagationPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Condiții de propagare", parent)
        self.estimator = PropagationEstimator()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.refresh(False))
        self._worker_thread = None
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.status = QLabel("Selectează o bandă pentru actualizare.")
        self.button = QPushButton("Actualizează")
        self.button.clicked.connect(lambda: self.refresh(True))
        top.addWidget(self.status)
        top.addStretch()
        top.addWidget(self.button)
        layout.addLayout(top)
        self.metrics = QGridLayout()
        box = QGroupBox("Space Weather")
        box.setLayout(self.metrics)
        layout.addWidget(box)
        self.metric_labels = {}
        for i, name in enumerate(
            (
                "SFI",
                "SSN",
                "K Index",
                "A Index",
                "X-Ray Flux",
                "Proton Flux",
                "Electron Flux",
                "Auroral Activity",
                "Bz",
                "Bt",
                "Solar Wind",
                "Densitate",
                "Temperatură",
                "Ap",
            )
        ):
            label = QLabel(f"<b>{name}</b><br>—")
            label.setWordWrap(True)
            self.metrics.addWidget(label, i // 4, i % 4)
            self.metric_labels[name] = label
        self.table = QTableWidget(5, 6)
        self.table.setHorizontalHeaderLabels(("Bandă", "Interval frecvență", "Zi", "Noapte", "Scor", "Încredere"))
        self.table.setVerticalHeaderLabels(("80m", "40m", "20m", "15m", "10m"))
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    @staticmethod
    def _format_value(value):
        return "N/A" if value is None else value

    def schedule(self, band, frequency=None, delay=700):
        if band.strip():
            self.timer.start(delay)

    def refresh(self, force=True):
        self.button.setEnabled(False)
        self.status.setText("Se descarcă date…")
        thread = QThread(self)
        self._worker_thread = thread
        self.worker = Worker(force)
        self.worker.moveToThread(thread)
        thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.update_values)
        self.worker.finished.connect(thread.quit)
        self.worker.failed.connect(lambda: self.status.setText("Ultima actualizare nu a reușit."))
        self.worker.failed.connect(thread.quit)
        thread.finished.connect(lambda: self.button.setEnabled(True))
        thread.start()

    def update_values(self, w):
        self.status.setText(f"Actualizat · {w.observed_at_utc.astimezone(UTC):%d-%m-%Y %H:%M UTC}")
        vals = {
            "SFI": w.solar_flux,
            "SSN": w.sunspot_number,
            "K Index": w.kp_index,
            "A Index": w.a_index,
            "X-Ray Flux": w.xray_flux,
            "Proton Flux": w.proton_flux,
            "Electron Flux": w.electron_flux,
            "Auroral Activity": w.auroral_activity,
            "Bz": w.bz,
            "Bt": w.bt,
            "Solar Wind": w.solar_wind_speed,
            "Densitate": w.solar_wind_density,
            "Temperatură": w.solar_wind_temperature,
            "Ap": w.ap_index,
        }
        for k, v in vals.items():
            self.metric_labels[k].setText(f"<b>{k}</b><br>{self._format_value(v)}")
        for r, (band, (day, night)) in enumerate(self.estimator.calculate_hf(w, datetime.now(UTC)).items()):
            values = (
                band,
                frequency_range_for_band(band) or "N/A",
                day.rating,
                night.rating,
                f"{(day.score + night.score) / 2:.0f}/100",
                day.confidence.capitalize(),
            )
            for c, v in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(v))

    def shutdown(self):
        self.timer.stop()
        if self._worker_thread is not None and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(1000)
