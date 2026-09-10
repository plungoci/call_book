"""Live DX cluster spots, geolocated relative to the operator's own station.

Each spot arriving from the node is placed on the map of DXCC entities (see
``services.callsign_geocoder``) and turned into a distance and a beam heading
from the station's position — the same idea as the public "ham geocoding"
cluster front-ends, computed locally instead of fetched. Double-clicking a
spot loads it into the QSO form, which is the point of having it here rather
than in a browser.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, QThread, Signal
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
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import callsign_geocoder
from ..services.dx_cluster import DxClusterClient, DxClusterError, DxSpot
from ..utils.geo import format_bearing, format_distance_km

LOG = logging.getLogger(__name__)

COLUMNS = ("Ora UTC", "Frecvență", "Bandă", "Indicativ", "Entitate", "Distanță", "Azimut", "Spotter", "Comentariu")
ALL_BANDS = "Toate benzile"
ALL_CONTINENTS = "Toate continentele"
MAX_SPOTS = 500

_LOCATION_COLUMNS = frozenset({COLUMNS.index("Entitate"), COLUMNS.index("Distanță"), COLUMNS.index("Azimut")})
_RIGHT_ALIGNED_COLUMNS = frozenset({COLUMNS.index("Frecvență"), COLUMNS.index("Distanță"), COLUMNS.index("Azimut")})

_PRECISE_FOREGROUND = QColor("#7ee787")
_APPROXIMATE_FOREGROUND = QColor("#8b949e")
_UNKNOWN_FOREGROUND = QColor("#f85149")


class SpotReader(QObject):
    """Reads spots off a cluster connection until the socket is closed."""

    spot = Signal(object)
    connected = Signal()
    failed = Signal(str)
    finished = Signal()

    def __init__(self, client: DxClusterClient):
        super().__init__()
        self.client = client

    def run(self):
        try:
            self.client.connect()
            self.connected.emit()
            for spot in self.client.spots():
                self.spot.emit(spot)
        except DxClusterError as exc:
            self.failed.emit(str(exc))
        except Exception:
            LOG.warning("Citirea spoturilor DX cluster a eșuat.", exc_info=True)
            self.failed.emit("Eroare neașteptată la citirea spoturilor.")
        finally:
            self.finished.emit()


class DxClusterPanel(QGroupBox):
    """Spot table plus the connection controls for one cluster node."""

    spotSelected = Signal(str, float, str, str)

    def __init__(self, location_provider, callsign_provider, node_provider, parent=None):
        super().__init__("DX Cluster", parent)
        self.location_provider = location_provider
        self.callsign_provider = callsign_provider
        self.node_provider = node_provider
        self.spots: list[tuple[DxSpot, callsign_geocoder.CallsignLocation | None]] = []
        self.client: DxClusterClient | None = None
        self._thread: QThread | None = None
        self._reader: SpotReader | None = None

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_connection_row())
        layout.addLayout(self._build_filter_row())

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COLUMNS.index("Comentariu"), QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self._use_selected_spot)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.hint = QLabel(
            "Dublu-clic pe un spot îl încarcă în formularul QSO. Distanța și azimutul sunt aproximative "
            "când poziția vine din prefix (centrul entității DXCC), exacte când spotul conține un locator."
        )
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#8b949e")
        bottom.addWidget(self.hint, 1)
        self.use_button = QPushButton("Încarcă în formular")
        self.use_button.clicked.connect(self._use_selected_spot)
        bottom.addWidget(self.use_button)
        layout.addLayout(bottom)

    def _build_connection_row(self):
        row = QHBoxLayout()
        self.status = QLabel("Deconectat.")
        self.status.setWordWrap(True)
        self.connect_button = QPushButton("Conectează")
        self.connect_button.clicked.connect(self.toggle_connection)
        self.clear_button = QPushButton("Golește lista")
        self.clear_button.clicked.connect(self.clear_spots)
        row.addWidget(self.status, 1)
        row.addWidget(self.clear_button)
        row.addWidget(self.connect_button)
        return row

    def _build_filter_row(self):
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrează după indicativ, entitate sau comentariu…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._rebuild_table)
        row.addWidget(self.search, 1)

        self.band_filter = QComboBox()
        self.band_filter.addItem(ALL_BANDS)
        self.band_filter.currentTextChanged.connect(self._rebuild_table)
        row.addWidget(self.band_filter)

        self.continent_filter = QComboBox()
        self.continent_filter.addItem(ALL_CONTINENTS)
        self.continent_filter.addItems(callsign_geocoder.known_continents())
        self.continent_filter.currentTextChanged.connect(self._rebuild_table)
        row.addWidget(self.continent_filter)

        self.located_only = QCheckBox("Doar cele localizate")
        self.located_only.setToolTip("Ascunde spoturile al căror prefix nu este în tabelul de entități.")
        self.located_only.toggled.connect(self._rebuild_table)
        row.addWidget(self.located_only)
        return row

    # --- connection -----------------------------------------------------
    @property
    def is_connected(self):
        return self._thread is not None and self._thread.isRunning()

    def toggle_connection(self):
        self.disconnect_from_node() if self.is_connected else self.connect_to_node()

    def connect_to_node(self):
        if self.is_connected:
            return
        callsign = (self.callsign_provider() or "").strip().upper()
        if not callsign:
            self.status.setText("Completează indicativul în Setări → Date operator înainte de conectare.")
            return
        host, port = self.node_provider()
        self.client = DxClusterClient(host, port, callsign)
        self.status.setText(f"Se conectează la {host}:{port}…")
        self.connect_button.setEnabled(False)

        thread = QThread(self)
        reader = SpotReader(self.client)
        reader.moveToThread(thread)
        thread.started.connect(reader.run)
        reader.connected.connect(lambda: self.status.setText(f"Conectat la {host}:{port} ca {callsign}."))
        reader.spot.connect(self.add_spot)
        reader.failed.connect(self._connection_failed)
        reader.finished.connect(thread.quit)
        thread.finished.connect(self._connection_closed)
        self._thread, self._reader = thread, reader
        thread.start()
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Deconectează")

    def disconnect_from_node(self):
        if self.client is not None:
            self.client.close()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
        self.status.setText("Deconectat.")

    def _connection_failed(self, message):
        self.status.setText(message)

    def _connection_closed(self):
        self._thread = None
        self._reader = None
        self.client = None
        self.connect_button.setText("Conectează")
        self.connect_button.setEnabled(True)
        if self.status.text().startswith("Conectat"):
            self.status.setText("Conexiunea s-a închis.")

    # --- spots ----------------------------------------------------------
    def add_spot(self, spot):
        """Store a spot with its computed position, newest first.

        Only the new row is inserted, rather than the whole table being
        rebuilt: on a busy evening the node sends a spot every few seconds,
        and re-creating several thousand table items each time would make the
        panel stutter for no reason.
        """
        if any(existing.key == spot.key for existing, _ in self.spots[:20]):
            return
        location = callsign_geocoder.locate(spot.dx_call, spot.comment, spot.locator)
        self.spots.insert(0, (spot, location))
        del self.spots[MAX_SPOTS:]
        if spot.band not in (self.band_filter.itemText(i) for i in range(self.band_filter.count())):
            self.band_filter.addItem(spot.band)
        visible = self.visible_spots()
        if visible and visible[0][0] is spot:
            self.table.insertRow(0)
            self._fill_row(0, spot, location)
        # A spot pushed off the end of the stored list takes its row with it.
        while self.table.rowCount() > len(visible):
            self.table.removeRow(self.table.rowCount() - 1)
        self._update_status_counts(len(visible))

    def clear_spots(self):
        self.spots.clear()
        self._rebuild_table()

    def visible_spots(self):
        """Return the stored spots passing the current filters, newest first."""
        text = self.search.text().strip().lower()
        band = self.band_filter.currentText()
        continent = self.continent_filter.currentText()
        visible = []
        for spot, location in self.spots:
            if band != ALL_BANDS and spot.band != band:
                continue
            if continent != ALL_CONTINENTS and (location is None or location.continent != continent):
                continue
            if self.located_only.isChecked() and location is None:
                continue
            haystack = f"{spot.dx_call} {spot.spotter} {spot.comment} {location.entity if location else ''}".lower()
            if text and text not in haystack:
                continue
            visible.append((spot, location))
        return visible

    def _fill_row(self, row, spot, location):
        latitude, longitude = self.location_provider()
        path = callsign_geocoder.path_from(location, latitude, longitude) if location else None
        entity = (location.entity if location else "necunoscut") + (
            f" · {location.locator}" if location and location.locator else ""
        )
        values = (
            f"{spot.spotted_at_utc:%H:%M}",
            f"{spot.frequency_mhz:.4f}".rstrip("0").rstrip(".") + " MHz",
            spot.band,
            spot.dx_call,
            entity,
            format_distance_km(path[0]) if path else "—",
            format_bearing(path[1]) if path else "—",
            spot.spotter,
            spot.comment,
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column in _LOCATION_COLUMNS:
                item.setForeground(QBrush(_entity_colour(location)))
            if column in _RIGHT_ALIGNED_COLUMNS:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, column, item)

    def _rebuild_table(self, *_):
        visible = self.visible_spots()
        self.table.setRowCount(len(visible))
        for row, (spot, location) in enumerate(visible):
            self._fill_row(row, spot, location)
        self._update_status_counts(len(visible))

    def _update_status_counts(self, visible_count):
        located = sum(1 for _, location in self.spots if location is not None)
        self.hint.setToolTip(f"{located} din {len(self.spots)} spoturi au o poziție cunoscută.")
        self.use_button.setEnabled(visible_count > 0)

    def selected_spot(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        visible = self.visible_spots()
        index = rows[0].row()
        return visible[index] if index < len(visible) else None

    def _use_selected_spot(self, *_):
        selection = self.selected_spot()
        if selection is None:
            return
        spot, location = selection
        self.spotSelected.emit(
            spot.dx_call,
            spot.frequency_mhz,
            spot.band,
            location.locator if location and location.locator else "",
        )

    def shutdown(self):
        self.disconnect_from_node()


def _entity_colour(location):
    if location is None:
        return _UNKNOWN_FOREGROUND
    return _PRECISE_FOREGROUND if location.is_precise else _APPROXIMATE_FOREGROUND


class DxClusterTab(QWidget):
    """Thin container so the panel can sit directly in a tab."""

    def __init__(self, panel, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panel)
