"""Headless tests for the local (terrestrial) weather client."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from call_book.services.local_weather_service import LocalWeatherError, LocalWeatherService


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass


class LocalWeatherServiceTests(TestCase):
    def test_fetch_reads_temperature_humidity_and_condition(self) -> None:
        payload = (
            b'{"current": {"temperature_2m": 21.3, "relative_humidity_2m": 55, "weather_code": 3}, '
            b'"current_units": {"temperature_2m": "\xc2\xb0C"}}'
        )
        metar_payload = b'[{"icaoId": "LRSB", "wspd": 12}]'
        with patch(
            "call_book.services.local_weather_service.curl_requests.get",
            side_effect=(FakeResponse(payload), FakeResponse(metar_payload)),
        ) as mock_get:
            result = LocalWeatherService().fetch(46.77, 23.6)
        self.assertEqual(result.temperature_c, 21.3)
        self.assertEqual(result.humidity_percent, 55)
        self.assertEqual(result.condition, "Înnorat")
        self.assertEqual(result.wind_speed_knots, 12)
        self.assertAlmostEqual(result.wind_speed_kmh or 0, 22.224)
        self.assertEqual(mock_get.call_args_list[0].kwargs.get("impersonate"), "chrome")
        self.assertEqual(mock_get.call_args_list[0].kwargs["params"]["latitude"], "46.7700")
        self.assertEqual(mock_get.call_args_list[1].kwargs["params"]["ids"], "LRSB")

    def test_fetch_raises_when_response_has_no_current_block(self) -> None:
        with (
            patch(
                "call_book.services.local_weather_service.curl_requests.get",
                return_value=FakeResponse(b'{"error": true, "reason": "bad request"}'),
            ),
            self.assertRaises(LocalWeatherError),
        ):
            LocalWeatherService().fetch(46.77, 23.6)

    def test_fetch_raises_on_malformed_json(self) -> None:
        with (
            patch(
                "call_book.services.local_weather_service.curl_requests.get",
                return_value=FakeResponse(b"not json"),
            ),
            self.assertRaises(LocalWeatherError),
        ):
            LocalWeatherService().fetch(46.77, 23.6)

    def test_unknown_weather_code_leaves_condition_unset(self) -> None:
        payload = b'{"current": {"temperature_2m": 10, "relative_humidity_2m": 40, "weather_code": 987}}'
        with patch("call_book.services.local_weather_service.curl_requests.get", return_value=FakeResponse(payload)):
            result = LocalWeatherService().fetch(46.77, 23.6)
        self.assertIsNone(result.condition)

    def test_unavailable_metar_leaves_wind_unset(self) -> None:
        weather = FakeResponse(
            b'{"current": {"temperature_2m": 10, "relative_humidity_2m": 40, "weather_code": 0}}'
        )
        with patch(
            "call_book.services.local_weather_service.curl_requests.get",
            side_effect=(weather, FakeResponse(b"[]")),
        ):
            result = LocalWeatherService().fetch(46.77, 23.6)
        self.assertIsNone(result.wind_speed_knots)
        self.assertIsNone(result.wind_speed_kmh)
