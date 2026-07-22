"""Compact Tk presentation for multi-provider space-weather conditions."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk

from propagation_models import SpaceWeatherData
from services.propagation_estimator import PropagationEstimator
from services.space_weather_service import SpaceWeatherService
from .tooltip import Tooltip


class PropagationPanel(ttk.LabelFrame):
    """Keeps valid readings visible while NOAA requests run in a worker thread."""

    _RATING_COLORS = {
        "Foarte slabă": "#b91c1c",
        "Slabă": "#c2410c",
        "Moderată": "#a16207",
        "Bună": "#15803d",
        "Foarte bună": "#166534",
        "Excelentă": "#0369a1",
    }

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, text="Condiții de propagare", padding=8)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="space-weather")
        self.request_id = 0
        self.after_id: str | None = None
        self.closing = False
        self._estimator = PropagationEstimator()

        top = ttk.Frame(self)
        top.pack(fill="x")
        self.status = tk.StringVar(value="Selectează o bandă pentru actualizarea datelor disponibile.")
        ttk.Label(top, textvariable=self.status).pack(side="left")
        self.refresh_button = ttk.Button(top, text="Actualizează", command=lambda: self.refresh(force=True))
        self.refresh_button.pack(side="right")
        Tooltip(self.refresh_button, "Descarcă date din sursele disponibile și actualizează tabelul fără a recrea panoul.")

        weather_frame = ttk.LabelFrame(self, text="Space Weather", padding=6)
        weather_frame.pack(fill="x", pady=(8, 4))
        self.updated = tk.StringVar(value="—")
        self.source = tk.StringVar(value="—")
        self._metric_values = {name: tk.StringVar(value="—") for name in (
            "SFI", "SSN", "K Index", "A Index", "X-Ray Flux", "Proton Flux",
            "Electron Flux", "Auroral Activity", "Bz", "Bt", "Solar Wind", "Densitate particule", "Temperatură vânt", "Ap",
        )}
        self._add_pair(weather_frame, 0, "Actualizat (UTC)", self.updated)
        self._add_pair(weather_frame, 1, "Sursă", self.source)
        metric_names = list(self._metric_values)
        for index, name in enumerate(metric_names):
            row, column = divmod(index, 2)
            frame = ttk.Frame(weather_frame)
            frame.grid(row=row + 2, column=column, sticky="ew", padx=(0, 18), pady=1)
            ttk.Label(frame, text=f"{name}:", width=20).pack(side="left")
            ttk.Label(frame, textvariable=self._metric_values[name]).pack(side="left")
        weather_frame.columnconfigure(0, weight=1)
        weather_frame.columnconfigure(1, weight=1)

        hf_frame = ttk.LabelFrame(self, text="HF Conditions", padding=6)
        hf_frame.pack(fill="x", pady=4)
        self.conditions = ttk.Frame(hf_frame)
        self.conditions.pack(fill="x")
        for column, heading in enumerate(("Bandă", "Zi", "Noapte")):
            ttk.Label(self.conditions, text=heading).grid(row=0, column=column, sticky="w", padx=(0, 22))
        self._condition_values: dict[str, tuple[tk.StringVar, tk.StringVar]] = {}
        self._condition_labels: dict[str, tuple[tk.Label, tk.Label]] = {}
        for row, band in enumerate(("80m", "40m", "20m", "15m", "10m"), start=1):
            ttk.Label(self.conditions, text=band).grid(row=row, column=0, sticky="w", padx=(0, 22))
            day, night = tk.StringVar(value="—"), tk.StringVar(value="—")
            day_label = tk.Label(self.conditions, textvariable=day, anchor="w")
            night_label = tk.Label(self.conditions, textvariable=night, anchor="w")
            day_label.grid(row=row, column=1, sticky="w", padx=(0, 22))
            night_label.grid(row=row, column=2, sticky="w")
            self._condition_values[band] = (day, night)
            self._condition_labels[band] = (day_label, night_label)

        geomagnetic = ttk.LabelFrame(self, text="Geomagnetic", padding=6)
        geomagnetic.pack(fill="x", pady=(4, 0))
        self._geomagnetic = tk.StringVar(value="Aurora: —    Bz: —    Solar Wind: —")
        ttk.Label(geomagnetic, textvariable=self._geomagnetic).pack(anchor="w")

    @staticmethod
    def _add_pair(parent: ttk.Frame, row: int, label: str, value: tk.StringVar) -> None:
        ttk.Label(parent, text=f"{label}:", width=20).grid(row=row, column=0, sticky="w", pady=1)
        ttk.Label(parent, textvariable=value).grid(row=row, column=1, sticky="w", pady=1)

    def schedule(self, band: str, frequency: float | None = None, delay: int = 700) -> None:
        """Debounce form changes; the compact forecast always contains all HF bands."""
        del frequency
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except tk.TclError:
                pass
        if not (band or "").strip():
            return
        self.request_id += 1
        request_id = self.request_id
        self.after_id = self.after(delay, lambda: self._start(request_id, force=False))

    def refresh(self, force: bool = True) -> None:
        """Request fresh NOAA data without rebuilding any widget."""
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except tk.TclError:
                pass
        self.request_id += 1
        self._start(self.request_id, force=force)

    def _start(self, request_id: int, force: bool) -> None:
        if self.closing or request_id != self.request_id:
            return
        self.status.set("Se descarcă date din sursele disponibile…")
        self.refresh_button.config(state="disabled")
        future = self.executor.submit(SpaceWeatherService().fetch, force)
        future.add_done_callback(lambda result: self.after(0, lambda: self._finish(request_id, result)))

    def _finish(self, request_id: int, future: object) -> None:
        if self.closing or request_id != self.request_id:
            return
        self.refresh_button.config(state="normal")
        try:
            self.update_values(future.result())  # type: ignore[union-attr]
            self.status.set("Actualizat")
        except Exception:
            self.status.set("Ultima actualizare nu a reușit.")

    def update_values(self, weather: SpaceWeatherData) -> None:
        """Apply a successful result in place and retain it for future failures."""
        self.updated.set(weather.observed_at_utc.astimezone(timezone.utc).strftime("%d-%m-%Y %H:%M UTC"))
        self.source.set(weather.source or "—")
        values = {
            "SFI": weather.solar_flux,
            "SSN": weather.sunspot_number,
            "K Index": weather.kp_index,
            "A Index": weather.a_index,
            "X-Ray Flux": weather.xray_flux,
            "Proton Flux": weather.proton_flux,
            "Electron Flux": weather.electron_flux,
            "Auroral Activity": weather.auroral_activity,
            "Bz": weather.bz,
            "Bt": weather.bt,
            "Solar Wind": weather.solar_wind_speed,
            "Densitate particule": weather.solar_wind_density,
            "Temperatură vânt": weather.solar_wind_temperature,
            "Ap": weather.ap_index,
        }
        for name, value in values.items():
            key = {"SFI":"solar_flux", "SSN":"sunspot_number", "K Index":"kp_index", "A Index":"a_index", "X-Ray Flux":"xray_flux", "Proton Flux":"proton_flux", "Electron Flux":"electron_flux", "Auroral Activity":"auroral_activity", "Bz":"bz", "Bt":"bt", "Solar Wind":"solar_wind_speed", "Densitate particule":"solar_wind_density", "Temperatură vânt":"solar_wind_temperature", "Ap":"ap_index"}[name]
            measurement = weather.measurement(key)
            self._metric_values[name].set(self._format_measurement(value, measurement.unit if measurement else "", measurement.source if measurement else "—", measurement.age_seconds if measurement else None))
        self._geomagnetic.set(
            f"Aurora: {self._format_value(weather.auroral_activity)}%    "
            f"Bz: {self._format_value(weather.bz)} nT    "
            f"Solar Wind: {self._format_value(weather.solar_wind_speed)} km/s"
        )
        for band, (day, night) in self._estimator.calculate_hf(weather, datetime.now(timezone.utc)).items():
            day_value, night_value = self._condition_values[band]
            day_label, night_label = self._condition_labels[band]
            day_value.set(day.rating)
            night_value.set(night.rating)
            day_label.config(fg=self._RATING_COLORS.get(day.rating, ""))
            night_label.config(fg=self._RATING_COLORS.get(night.rating, ""))

    @staticmethod
    def _format_value(value: float | str | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:g}" if isinstance(value, float) else str(value)

    @classmethod
    def _format_measurement(cls, value: float | str | None, unit: str, source: str, age_seconds: int | None) -> str:
        if value is None:
            return "N/A (fără sursă validă)"
        age = "?" if age_seconds is None else (f"{age_seconds // 60} min" if age_seconds < 3600 else f"{age_seconds // 3600} h")
        return f"{cls._format_value(value)} {unit} [{source}, {age}]".strip()

    def shutdown(self) -> None:
        self.closing = True
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except tk.TclError:
                pass
        self.executor.shutdown(wait=False, cancel_futures=True)
