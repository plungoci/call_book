"""Headless tests for NOAA parsing/cache and compact propagation estimates."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import TestCase
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QHeaderView

from call_book.propagation_models import SpaceWeatherData
from call_book.services.band_detector import BandDetector
from call_book.services.propagation_cache import PropagationCache
from call_book.services.propagation_estimator import PropagationEstimator, evaluate_band_conditions
from call_book.services.space_weather_service import (
    GFZ_ENDPOINT,
    HAMQSL_ENDPOINT,
    NOAA_ENDPOINTS,
    NOAA_FALLBACK_ENDPOINTS,
    NRCAN_ENDPOINT,
    SILSO_ENDPOINT,
    SpaceWeatherError,
    SpaceWeatherService,
    _latest,
    parse_gfz_nowcast,
    parse_hamqsl_solar_xml,
    parse_nrcan_solar_flux,
    parse_silso_daily_csv,
)
from call_book.ui.propagation_panel import PropagationPanel, Worker
from call_book.validators import frequency_range_for_band


class SpaceWeatherTests(TestCase):
    def test_fetch_uses_fresh_cache(self) -> None:
        with TemporaryDirectory() as directory:
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            service.cache.write_json(
                service.cache.weather_path(),
                {
                    "kp_index": 3,
                    "a_index": 12,
                    "solar_flux": 145,
                    "sunspot_number": 96,
                    "radio_blackout_level": None,
                    "source": "NOAA SWPC JSON",
                    "observed_at_utc": datetime.now(UTC).isoformat(),
                },
            )
            self.assertEqual(service.fetch().solar_flux, 145)

    def test_error_is_propagated_when_no_valid_cache_exists(self) -> None:
        with TemporaryDirectory() as directory:
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            service._get = Mock(side_effect=SpaceWeatherError("timeout"))
            with self.assertRaises(SpaceWeatherError):
                service.fetch(force=True)

    def test_nrcan_solar_flux_overrides_noaas_when_both_are_available(self) -> None:
        # NOAA's solar_flux is behind an AWS WAF bot challenge that's not
        # always solvable (see space_weather_service module docstring); NRCan
        # is treated as the preferred source when it does respond, the same
        # way SILSO/GFZ already take priority over NOAA's own copies.
        def fake_get(url: str, as_json: bool = True) -> Any:
            if url == NOAA_ENDPOINTS["solar"]:
                return [{"f10.7": "145", "ssn": "96"}]
            if url == NRCAN_ENDPOINT:
                return "20260729 230000 2461251.447 2313.86 0145.1 0149.5 0134.5"
            if url in (SILSO_ENDPOINT, GFZ_ENDPOINT):
                raise SpaceWeatherError("indisponibil")
            return [] if as_json else ""

        with TemporaryDirectory() as directory:
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            service._get = Mock(side_effect=fake_get)
            weather = service.fetch(force=True)
            self.assertEqual(weather.solar_flux, 149.5)

    def test_get_reports_a_snippet_when_a_200_response_is_not_valid_json(self) -> None:
        # Regression test: a WAF/proxy/captive-portal answering with an empty
        # or non-JSON 200 response previously surfaced only as an opaque
        # "Expecting value: line 1 column 1 (char 0)", indistinguishable from
        # a genuinely broken feed. The response body must now be visible too.
        class FakeResponse:
            content = b"<html>blocked</html>"

            def raise_for_status(self):
                pass

        with (
            TemporaryDirectory() as directory,
            patch("call_book.services.space_weather_service.curl_requests.get", return_value=FakeResponse()),
        ):
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            with self.assertRaises(SpaceWeatherError) as ctx:
                service._get("https://example.invalid/data.json")
            self.assertIn("blocked", str(ctx.exception))

    def test_get_reports_a_snippet_when_the_response_is_too_large(self) -> None:
        # Regression test: an oversized response (e.g. a large HTML block page
        # substituted by a firewall/proxy for the tiny expected CSV/text feed)
        # previously raised a bare "Răspuns prea mare" with no way to tell a
        # block page apart from a provider that genuinely changed its format.
        class FakeResponse:
            content = b"<html>blocked page too large" + b" filler" * 1_200_000

            def raise_for_status(self):
                pass

        with (
            TemporaryDirectory() as directory,
            patch("call_book.services.space_weather_service.curl_requests.get", return_value=FakeResponse()),
        ):
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            with self.assertRaises(SpaceWeatherError) as ctx:
                service._get("https://example.invalid/data.csv", as_json=False)
            self.assertIn("blocked page too large", str(ctx.exception))

    def test_get_impersonates_a_real_browser_to_get_past_noaas_bot_challenge(self) -> None:
        # Regression test: NOAA SWPC sits behind an AWS WAF bot-management
        # challenge that answers plain HTTP clients (verified with curl, not
        # just this app) with an empty HTTP 202, regardless of headers — only
        # a request whose TLS/HTTP2 fingerprint matches a real browser gets
        # through. Losing the "impersonate=chrome" kwarg silently regresses to
        # the empty-response bug even though the code still compiles and runs.
        class FakeResponse:
            content = b'{"ok": true}'

            def raise_for_status(self):
                pass

        with (
            TemporaryDirectory() as directory,
            patch(
                "call_book.services.space_weather_service.curl_requests.get", return_value=FakeResponse()
            ) as mock_get,
        ):
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            service._get("https://example.invalid/data.json")
            self.assertEqual(mock_get.call_args.kwargs.get("impersonate"), "chrome")

    def test_fetch_does_not_probe_a_raw_socket_before_the_real_request(self) -> None:
        # Regression test: a prior raw socket.create_connection() pre-check
        # bypassed any HTTP(S) proxy that urlopen() itself would respect,
        # falsely reporting "no internet connection" on proxied networks even
        # though the real request would have succeeded.
        with TemporaryDirectory() as directory, patch("socket.create_connection", side_effect=OSError("blocked")):
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            service._get = Mock(return_value=[{"kp_index": "3", "a_running": "12"}])
            weather = service.fetch(force=True)
            self.assertEqual(weather.kp_index, 3)


class PropagationEstimatorTests(TestCase):
    def setUp(self) -> None:
        now = datetime.now(UTC)
        self.weather = SpaceWeatherData(2, 8, 150, None, None, "fixture", now, now)

    def test_hf_table_contains_all_compact_bands(self) -> None:
        conditions = PropagationEstimator().calculate_bands(self.weather, datetime.now(UTC))
        self.assertEqual(tuple(conditions), ("160m", "80m", "40m", "20m", "15m", "10m", "2m", "70cm"))
        self.assertLess(conditions["80m"][0].score, conditions["80m"][1].score)

    def test_vhf_uhf_rows_use_the_flat_line_of_sight_estimate(self) -> None:
        # 2m/70cm aren't driven by solar indices, so day and night must match.
        conditions = PropagationEstimator().calculate_bands(self.weather, datetime.now(UTC))
        for band in ("2m", "70cm"):
            day, night = conditions[band]
            self.assertEqual(day.score, night.score)
            self.assertIn("line-of-sight", " ".join(day.warnings).lower())

    def test_existing_vhf_warnings_are_preserved(self) -> None:
        condition = evaluate_band_conditions("6m", self.weather, datetime.now(UTC))
        self.assertIn("Sporadic", " ".join(condition.warnings))

    def test_unavailable_values_are_displayed_clearly(self) -> None:
        self.assertEqual(PropagationPanel._format_value(None), "N/A")

    def test_hf_table_columns_size_to_fit_their_header_text(self) -> None:
        # Regression test: fixed default column widths clipped longer headers
        # like "Interval frecvență" (rendered as "nterval frecvenți").
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QApplication.instance() or QApplication([])
        panel = PropagationPanel()
        header = panel.table.horizontalHeader()
        self.assertEqual(header.sectionResizeMode(1), QHeaderView.ResizeMode.ResizeToContents)
        # Regression test: stretching the last column ("Încredere") made it
        # balloon to fill any leftover panel width instead of fitting its content.
        self.assertFalse(header.stretchLastSection())

    def test_worker_logs_the_fetch_failure_before_signaling(self) -> None:
        # Regression test: a bare "except Exception: self.failed.emit()" gave
        # no way to diagnose why "Ultima actualizare nu a reușit." happened.
        worker = Worker(force=True)
        with (
            patch.object(SpaceWeatherService, "fetch", side_effect=SpaceWeatherError("boom")),
            self.assertLogs("call_book.ui.propagation_panel", level="WARNING") as logs,
        ):
            worker.run()
        self.assertIn("boom", logs.output[0])

    def test_institutional_text_parsers_use_latest_valid_values(self) -> None:
        self.assertEqual(parse_silso_daily_csv("# header\n2025; 1; 1; 2025.0; 99; 2; 1\n"), 99)
        # Real rows are "YYYY MM DD hh.h hh._m days days_m Kp ap D" (10 columns).
        self.assertEqual(parse_gfz_nowcast("# header\n2026 07 30 18.0 18.250 34333 34333.760 2.3 12 1\n"), (2.3, 12))

    def test_gfz_nowcast_skips_missing_data_sentinel_rows(self) -> None:
        # Regression test: GFZ marks a missing reading as Kp=-1.000/ap=-1 (its
        # documented sentinel), and the trailing D (definitive-data) flag was
        # previously misread as ap, and ap misread as Kp. Both bugs produced a
        # plausible-looking but wrong "K Index: -1.0 / Ap: 0.0" in the UI.
        payload = (
            "2026 07 30 15.0 15.250 34333 34333.635 2.7 12 1\n2026 07 30 21.0 21.250 34333 34333.885 -1.000 -1 0\n"
        )
        self.assertEqual(parse_gfz_nowcast(payload), (2.7, 12))

    def test_nrcan_solar_flux_reads_the_latest_adjusted_flux_column(self) -> None:
        # Real sample from spaceweather.gc.ca/solar_flux_data/daily_flux_values/
        # fluxtable.txt: "fluxdate fluxtime fluxjulian fluxcarrington fluxobsflux
        # fluxadjflux fluxursi" — fluxadjflux (6th column, index 5) is the
        # 1 AU-corrected value ham-radio SFI reports refer to as "solar flux".
        payload = (
            "20260729    200000      2461251.322   2313.86         0142.8       0147.1       0132.4    \n"
            "20260729    230000      2461251.447   2313.86         0145.1       0149.5       0134.5"
        )
        self.assertEqual(parse_nrcan_solar_flux(payload), 149.5)

    def test_hamqsl_solar_xml_reads_metrics_noaa_could_not_supply(self) -> None:
        # Real sample from hamqsl.com/solarxml.php.
        payload = """<solar>
<solardata>
<source url="http://www.hamqsl.com/solar.html">N0NBH</source>
<updated> 30 Jul 2026 1706 GMT</updated>
<solarflux>143</solarflux>
<aindex> 5</aindex>
<kindex> 1</kindex>
<kindexnt>No Report</kindexnt>
<xray>M1.8</xray>
<sunspots>141</sunspots>
<heliumline>129.2</heliumline>
<protonflux>13</protonflux>
<electonflux>1580</electonflux>
<aurora> 1</aurora>
<normalization>1.99</normalization>
<latdegree>67.5</latdegree>
<solarwind>329.6</solarwind>
<magneticfield> -2.0</magneticfield>
<geomagfield>VR QUIET</geomagfield>
<signalnoise>S0-S1</signalnoise>
<fof2/>
<muffactor/>
<muf>NoRpt</muf>
</solardata>
</solar>"""
        result = parse_hamqsl_solar_xml(payload)
        self.assertEqual(result["a_index"], 5)
        assert result["xray_flux"] is not None
        self.assertAlmostEqual(result["xray_flux"], 1.8e-5)
        self.assertEqual(result["proton_flux"], 13)
        self.assertEqual(result["electron_flux"], 1580)
        self.assertEqual(result["solar_wind_speed"], 329.6)
        self.assertEqual(result["bz"], -2.0)
        # HamQSL's "aurora" is a unitless 1-10 activity index, not the
        # OVATION percentage auroral_activity represents elsewhere — must
        # not be silently mapped in under the wrong unit.
        self.assertNotIn("aurora", result)
        self.assertNotIn("auroral_activity", result)

    def test_hamqsl_only_fills_gaps_noaa_left_empty(self) -> None:
        def fake_get(url: str, as_json: bool = True) -> Any:
            if url == NOAA_ENDPOINTS["kp"]:
                return [{"kp_index": "3", "a_running": "77"}]
            if url == HAMQSL_ENDPOINT:
                return (
                    "<solar><solardata><aindex>5</aindex><xray>M1.8</xray>"
                    "<protonflux>13</protonflux><electonflux>1580</electonflux>"
                    "<solarwind>329.6</solarwind><magneticfield>-2.0</magneticfield>"
                    "</solardata></solar>"
                )
            if url in (SILSO_ENDPOINT, GFZ_ENDPOINT, NRCAN_ENDPOINT):
                raise SpaceWeatherError("indisponibil")
            return [] if as_json else ""

        with TemporaryDirectory() as directory:
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            service._get = Mock(side_effect=fake_get)
            weather = service.fetch(force=True)
            # a_index came from NOAA's own "kp" endpoint (a_running=77) — HamQSL
            # (aindex=5) must not clobber a value NOAA already supplied.
            self.assertEqual(weather.a_index, 77)
            # xray_flux/proton_flux/electron_flux/solar_wind_speed/bz had no
            # NOAA value at all in this scenario, so HamQSL fills them in.
            assert weather.xray_flux is not None
            self.assertAlmostEqual(weather.xray_flux, 1.8e-5)
            self.assertEqual(weather.proton_flux, 13)
            self.assertEqual(weather.electron_flux, 1580)
            self.assertEqual(weather.solar_wind_speed, 329.6)
            self.assertEqual(weather.bz, -2.0)

    def test_band_detector_covers_requested_hf_vhf_and_uhf_bands(self) -> None:
        cases = (
            (1.8, "160m"),
            (3.6, "80m"),
            (5.3, "60m"),
            (7.0, "40m"),
            (10.1, "30m"),
            (14.2, "20m"),
            (18.1, "17m"),
            (21.1, "15m"),
            (24.9, "12m"),
            (28.0, "10m"),
            (50.0, "6m"),
            (70.0, "4m"),
            (144.0, "2m"),
            (430.0, "70cm"),
        )
        for frequency, band in cases:
            self.assertEqual(BandDetector.frequency_to_band(frequency), band)
        self.assertIsNone(BandDetector.frequency_to_band(999))

    def test_frequency_ranges_are_available_for_propagation_bands(self) -> None:
        expected_ranges = {
            "160m": "1.8–2 MHz",
            "80m": "3.5–4 MHz",
            "40m": "7–7.3 MHz",
            "20m": "14–14.35 MHz",
            "15m": "21–21.45 MHz",
            "10m": "28–29.7 MHz",
            "2m": "144–148 MHz",
            "70cm": "430–440 MHz",
        }
        for band, expected_range in expected_ranges.items():
            self.assertEqual(frequency_range_for_band(band), expected_range)

    def test_parser_reads_each_noaa_product(self) -> None:
        with TemporaryDirectory() as directory:
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            products = {
                "kp": [{"kp_index": "3", "a_running": "12"}],
                "solar": [{"f10.7": "145", "ssn": "96"}],
                "xray": [{"observed_flux": "0.000001"}],
                "proton": [{"flux": "3.5"}],
                "electron": [{"flux": "42"}],
                "plasma": [["time_tag", "speed"], ["2026-07-22T12:00:00Z", "410"]],
                "magnetic": [["time_tag", "bz_gsm"], ["2026-07-22T12:00:00Z", "-2.1"]],
                "alerts": [],
            }
            service._get = Mock(
                side_effect=lambda url: products[
                    next(name for name, endpoint in NOAA_ENDPOINTS.items() if endpoint == url)
                ]
            )
            weather = service.fetch(force=True)
            self.assertEqual(
                (weather.solar_flux, weather.sunspot_number, weather.kp_index, weather.a_index), (145, 96, 3, 12)
            )
            self.assertEqual((weather.solar_wind_speed, weather.bz), (410, -2.1))

    def test_noaa_wind_endpoints_use_bounded_published_seven_day_feeds(self) -> None:
        self.assertEqual(
            NOAA_ENDPOINTS["plasma"],
            "https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json",
        )
        self.assertEqual(
            NOAA_ENDPOINTS["magnetic"],
            "https://services.swpc.noaa.gov/products/solar-wind/mag-7-day.json",
        )
        self.assertNotIn("plasma", NOAA_FALLBACK_ENDPOINTS)
        self.assertNotIn("magnetic", NOAA_FALLBACK_ENDPOINTS)

    def test_swpc_header_table_and_field_aliases_use_latest_valid_reading(self) -> None:
        rows = [
            ["time_tag", "proton_density", "solar_wind_speed", "temperature"],
            ["2026-07-22T11:00:00Z", None, "bad", "-1"],
            ["2026-07-22T12:00:00Z", "4.6", "503", "142000"],
        ]
        self.assertEqual(_latest(rows, ("density", "proton_density")), 4.6)
        self.assertEqual(_latest(rows, ("speed", "solar_wind_speed")), 503)
        self.assertEqual(_latest(rows, ("temperature",)), 142000)

    def test_missing_wind_values_do_not_request_retired_fallback_feeds(self) -> None:
        with TemporaryDirectory() as directory:
            service = SpaceWeatherService(PropagationCache(Path(directory)))
            products = {
                NOAA_ENDPOINTS["solar"]: [{"f10.7": "145"}],
                NOAA_ENDPOINTS["plasma"]: [["time_tag", "speed"], ["2026-07-22T12:00:00Z", None]],
            }
            service._get = Mock(side_effect=lambda url, as_json=True: products.get(url, []))
            weather = service.fetch(force=True)
            self.assertIsNone(weather.solar_wind_speed)
            self.assertNotIn("plasma-2-hour", " ".join(call.args[0] for call in service._get.call_args_list))
