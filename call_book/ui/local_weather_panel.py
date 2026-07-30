"""Thread-safe Qt panel showing the station's local (terrestrial) weather."""

import logging

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QVBoxLayout

from ..services.local_weather_service import LocalWeatherService

LOG = logging.getLogger(__name__)


class Worker(QObject):
    finished = Signal(object)
    failed = Signal()

    def __init__(self, latitude, longitude):
        super().__init__()
        self.latitude = latitude
        self.longitude = longitude

    def run(self):
        try:
            self.finished.emit(LocalWeatherService().fetch(self.latitude, self.longitude))
        except Exception:
            LOG.warning("Actualizarea vremii locale a eșuat.", exc_info=True)
            self.failed.emit()


class LocalWeatherPanel(QGroupBox):
    def __init__(self, location_provider, parent=None):
        super().__init__("Vreme locală", parent)
        self.location_provider = location_provider
        self._worker_thread = None
        layout = QVBoxLayout(self)
        self.status = QLabel("Neactualizat.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        form = QFormLayout()
        self.temperature_label = QLabel("N/A")
        self.humidity_label = QLabel("N/A")
        self.condition_label = QLabel("N/A")
        self.wind_label = QLabel("N/A")
        form.addRow("Temperatură", self.temperature_label)
        form.addRow("Umiditate", self.humidity_label)
        form.addRow("Condiții", self.condition_label)
        form.addRow("Vânt aeroport Sibiu", self.wind_label)
        layout.addLayout(form)
        layout.addStretch()

    def refresh(self):
        latitude, longitude = self.location_provider()
        if latitude is None or longitude is None:
            self.status.setText("Locația stației nu este setată (Setări → Date operator).")
            return
        self.status.setText("Se descarcă date…")
        thread = QThread(self)
        self._worker_thread = thread
        self.worker = Worker(latitude, longitude)
        self.worker.moveToThread(thread)
        thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.update_values)
        self.worker.finished.connect(thread.quit)
        self.worker.failed.connect(lambda: self.status.setText("Ultima actualizare nu a reușit."))
        self.worker.failed.connect(thread.quit)
        thread.start()

    def update_values(self, w):
        self.status.setText("Actualizat.")
        self.temperature_label.setText(f"{w.temperature_c:.1f} °C" if w.temperature_c is not None else "N/A")
        self.humidity_label.setText(f"{w.humidity_percent:.0f}%" if w.humidity_percent is not None else "N/A")
        self.condition_label.setText(w.condition or "N/A")
        self.wind_label.setText(
            f"{w.wind_speed_knots:.0f} kt / {w.wind_speed_kmh:.1f} km/h" if w.wind_speed_knots is not None else "N/A"
        )

    def shutdown(self):
        if self._worker_thread is not None and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(1000)
