"""Headless tests for the local (terrestrial) weather client."""

from __future__ import annotations

import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from call_book.services.local_weather_service import LocalWeatherError, LocalWeatherService


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass


_WEATHER_PAYLOAD = b'{"current": {"temperature_2m": 21.3, "relative_humidity_2m": 55, "weather_code": 3}}'
_METAR_PAYLOAD = b'[{"icaoId": "LRSB", "altim": 1017.6, "wspd": 12, "wdir": 270}]'


class LocalWeatherServiceTests(TestCase):
    def test_fetch_reads_temperature_humidity_and_condition(self) -> None:
        payload = (
            b'{"current": {"temperature_2m": 21.3, "relative_humidity_2m": 55, "weather_code": 3, '
            b'"pressure_msl": 1017.6}, '
            b'"current_units": {"temperature_2m": "\xc2\xb0C"}}'
        )
        with (
            TemporaryDirectory() as directory,
            patch(
                "call_book.services.local_weather_service.curl_requests.get",
                side_effect=(FakeResponse(payload), FakeResponse(_METAR_PAYLOAD)),
            ) as mock_get,
        ):
            result = LocalWeatherService(Path(directory) / "metar.json").fetch(46.77, 23.6)
        self.assertEqual(result.temperature_c, 21.3)
        self.assertEqual(result.humidity_percent, 55)
        self.assertEqual(result.condition, "Înnorat")
        self.assertEqual(result.atmospheric_pressure_hpa, 1017.6)
        self.assertEqual(result.wind_speed_knots, 12)
        self.assertEqual(result.wind_direction_degrees, 270)
        self.assertAlmostEqual(result.wind_speed_kmh or 0, 22.224)
        self.assertEqual(mock_get.call_args_list[0].kwargs.get("impersonate"), "chrome")
        self.assertEqual(mock_get.call_args_list[0].kwargs["params"]["latitude"], "46.7700")
        self.assertNotIn("pressure_msl", mock_get.call_args_list[0].kwargs["params"]["current"])
        self.assertEqual(mock_get.call_args_list[1].kwargs["params"]["ids"], "LRSB")

    def test_fetch_raises_when_response_has_no_current_block(self) -> None:
        with (
            TemporaryDirectory() as directory,
            patch(
                "call_book.services.local_weather_service.curl_requests.get",
                return_value=FakeResponse(b'{"error": true, "reason": "bad request"}'),
            ),
            self.assertRaises(LocalWeatherError),
        ):
            LocalWeatherService(Path(directory) / "metar.json").fetch(46.77, 23.6)

    def test_fetch_raises_on_malformed_json(self) -> None:
        with (
            TemporaryDirectory() as directory,
            patch(
                "call_book.services.local_weather_service.curl_requests.get",
                return_value=FakeResponse(b"not json"),
            ),
            self.assertRaises(LocalWeatherError),
        ):
            LocalWeatherService(Path(directory) / "metar.json").fetch(46.77, 23.6)

    def test_unknown_weather_code_leaves_condition_unset(self) -> None:
        payload = b'{"current": {"temperature_2m": 10, "relative_humidity_2m": 40, "weather_code": 987}}'
        with (
            TemporaryDirectory() as directory,
            patch("call_book.services.local_weather_service.curl_requests.get", return_value=FakeResponse(payload)),
        ):
            result = LocalWeatherService(Path(directory) / "metar.json").fetch(46.77, 23.6)
        self.assertIsNone(result.condition)

    def test_unavailable_metar_leaves_pressure_and_wind_unset(self) -> None:
        # No cache file exists yet, and the METAR fetch itself returns
        # nothing usable, so there's no fallback value to reach for either.
        weather = FakeResponse(_WEATHER_PAYLOAD)
        with (
            TemporaryDirectory() as directory,
            patch(
                "call_book.services.local_weather_service.curl_requests.get",
                side_effect=(weather, FakeResponse(b"[]")),
            ),
        ):
            result = LocalWeatherService(Path(directory) / "metar.json").fetch(46.77, 23.6)
        self.assertIsNone(result.wind_speed_knots)
        self.assertIsNone(result.wind_speed_kmh)
        self.assertIsNone(result.wind_direction_degrees)
        self.assertIsNone(result.atmospheric_pressure_hpa)

    def test_metar_cache_avoids_a_second_network_request_within_the_refresh_interval(self) -> None:
        # Regression test: refetching Sibiu's METAR on every single weather
        # refresh (configurable down to every 1 minute) risked the aviation-
        # weather API rate-limiting/blocking the repeated requests, silently
        # blanking pressure/wind to N/A on automatic refreshes even though
        # the very first (manual) refresh had worked fine.
        with (
            TemporaryDirectory() as directory,
            patch(
                "call_book.services.local_weather_service.curl_requests.get",
                side_effect=(
                    FakeResponse(_WEATHER_PAYLOAD),
                    FakeResponse(_METAR_PAYLOAD),
                    FakeResponse(_WEATHER_PAYLOAD),
                ),
            ) as mock_get,
        ):
            service = LocalWeatherService(Path(directory) / "metar.json")
            first = service.fetch(46.77, 23.6)
            second = service.fetch(46.77, 23.6)
        self.assertEqual(mock_get.call_count, 3)  # not 4: the second METAR fetch was skipped
        self.assertEqual(second.atmospheric_pressure_hpa, first.atmospheric_pressure_hpa)
        self.assertEqual(second.wind_speed_knots, first.wind_speed_knots)
        self.assertEqual(second.wind_direction_degrees, first.wind_direction_degrees)

    def test_metar_falls_back_to_a_stale_cache_when_a_fresh_fetch_fails(self) -> None:
        # A transient failure (or a block from the provider) must not blank
        # out already-good data — the propagation panel keeps its last valid
        # reading the same way.
        with TemporaryDirectory() as directory:
            cache_path = Path(directory) / "metar.json"
            stale_but_within_fallback_window = time.time() - 25 * 60  # older than the 20-min refresh interval
            cached = {
                "fetched_at": stale_but_within_fallback_window,
                "pressure": 1013.0,
                "wind_speed": 5,
                "wind_direction": 180,
            }
            cache_path.write_text(json.dumps(cached), encoding="utf-8")
            with patch(
                "call_book.services.local_weather_service.curl_requests.get",
                side_effect=(FakeResponse(_WEATHER_PAYLOAD), FakeResponse(b"[]")),
            ):
                result = LocalWeatherService(cache_path).fetch(46.77, 23.6)
        self.assertEqual(result.atmospheric_pressure_hpa, 1013.0)
        self.assertEqual(result.wind_speed_knots, 5)
        self.assertEqual(result.wind_direction_degrees, 180)

    def test_metar_cache_older_than_the_fallback_window_is_not_used(self) -> None:
        with TemporaryDirectory() as directory:
            cache_path = Path(directory) / "metar.json"
            too_old = time.time() - 4 * 60 * 60  # older than the 3-hour fallback window
            cache_path.write_text(
                json.dumps({"fetched_at": too_old, "pressure": 1013.0, "wind_speed": 5, "wind_direction": 180}),
                encoding="utf-8",
            )
            with patch(
                "call_book.services.local_weather_service.curl_requests.get",
                side_effect=(FakeResponse(_WEATHER_PAYLOAD), FakeResponse(b"[]")),
            ):
                result = LocalWeatherService(cache_path).fetch(46.77, 23.6)
        self.assertIsNone(result.atmospheric_pressure_hpa)
