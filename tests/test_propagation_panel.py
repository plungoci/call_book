"""Headless tests for NOAA parsing/cache and compact propagation estimates."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock

from propagation_models import SpaceWeatherData
from services.propagation_cache import PropagationCache
from services.propagation_estimator import PropagationEstimator, evaluate_band_conditions
from services.band_detector import BandDetector
from services.space_weather_service import SpaceWeatherError, SpaceWeatherService
from ui.propagation_panel import PropagationPanel


class SpaceWeatherTests(TestCase):
    def test_fetch_uses_fresh_cache(self) -> None:
        with TemporaryDirectory() as directory:
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            service.cache.write_json(service.cache.weather_path(), {
                "kp_index": 3, "a_index": 12, "solar_flux": 145, "sunspot_number": 96,
                "radio_blackout_level": None, "source": "NOAA SWPC JSON",
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            })
            self.assertEqual(service.fetch().solar_flux, 145)

    def test_error_is_propagated_when_no_valid_cache_exists(self) -> None:
        with TemporaryDirectory() as directory:
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            service._get = Mock(side_effect=SpaceWeatherError("timeout"))
            with self.assertRaises(SpaceWeatherError):
                service.fetch(force=True)


class PropagationEstimatorTests(TestCase):
    def setUp(self) -> None:
        now = datetime.now(timezone.utc)
        self.weather = SpaceWeatherData(2, 8, 150, None, None, "fixture", now, now)

    def test_hf_table_contains_all_compact_bands(self) -> None:
        conditions = PropagationEstimator().calculate_hf(self.weather, datetime.now(timezone.utc))
        self.assertEqual(tuple(conditions), ("80m", "40m", "20m", "15m", "10m"))
        self.assertLess(conditions["80m"][0].score, conditions["80m"][1].score)

    def test_existing_vhf_warnings_are_preserved(self) -> None:
        condition = evaluate_band_conditions("6m", self.weather, datetime.now(timezone.utc))
        self.assertIn("Sporadic", " ".join(condition.warnings))

    def test_unavailable_values_are_displayed_clearly(self) -> None:
        self.assertEqual(PropagationPanel._format_value(None), "Unavailable")

    def test_band_detector_covers_requested_hf_vhf_and_uhf_bands(self) -> None:
        cases = (
            (1.8, "160m"), (3.6, "80m"), (5.3, "60m"), (7.0, "40m"),
            (10.1, "30m"), (14.2, "20m"), (18.1, "17m"), (21.1, "15m"),
            (24.9, "12m"), (28.0, "10m"), (50.0, "6m"), (70.0, "4m"),
            (144.0, "2m"), (430.0, "70cm"),
        )
        for frequency, band in cases:
            self.assertEqual(BandDetector.frequency_to_band(frequency), band)
        self.assertIsNone(BandDetector.frequency_to_band(999))

    def test_parser_reads_each_noaa_product(self) -> None:
        with TemporaryDirectory() as directory:
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            products = {
                "kp": [{"kp_index": "3", "a_running": "12"}],
                "solar": [{"f10.7": "145", "ssn": "96"}],
                "xray": [{"observed_flux": "0.000001"}],
                "proton": [{"flux": "3.5"}], "electron": [{"flux": "42"}],
                "plasma": [{"speed": "410", "density": "5.2"}],
                "magnetic": [{"bz_gsm": "-2.1"}],
                "aurora": {"coordinates": [{"probability": "18"}]}, "alerts": [],
            }
            service._get = Mock(side_effect=lambda url: products[next(name for name, endpoint in __import__("services.space_weather_service", fromlist=["NOAA_ENDPOINTS"]).NOAA_ENDPOINTS.items() if endpoint == url)])
            weather = service.fetch(force=True)
            self.assertEqual((weather.solar_flux, weather.sunspot_number, weather.kp_index, weather.a_index), (145, 96, 3, 12))
            self.assertEqual((weather.solar_wind_speed, weather.solar_wind_density, weather.bz), (410, 5.2, -2.1))
