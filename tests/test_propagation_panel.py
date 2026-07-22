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

    def test_unavailable_values_are_displayed_as_na(self) -> None:
        self.assertEqual(PropagationPanel._format_value(None), "N/A")
