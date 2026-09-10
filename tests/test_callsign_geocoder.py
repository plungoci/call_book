"""Tests for placing a spotted callsign on the map."""

from __future__ import annotations

import unittest

from call_book.services.callsign_geocoder import (
    base_callsign,
    find_entity,
    find_locator,
    known_continents,
    locate,
    path_from,
)
from tests.support import require

SIBIU = (45.79, 24.15)


def entity_of(callsign: str):
    """The DXCC entity for a callsign the test expects to be listed."""
    return require(find_entity(callsign), callsign)


def location_of(callsign: str, **kwargs):
    """The position for a callsign the test expects to be placeable."""
    return require(locate(callsign, **kwargs), callsign)


class BaseCallsignTests(unittest.TestCase):
    def test_a_plain_callsign_is_returned_unchanged(self) -> None:
        self.assertEqual(base_callsign("yo3abc"), "YO3ABC")

    def test_a_leading_prefix_decides_where_the_station_is(self) -> None:
        self.assertEqual(base_callsign("DL/YO3ABC/P"), "DL")

    def test_a_trailing_prefix_is_used_as_well(self) -> None:
        self.assertEqual(base_callsign("YO3ABC/DL"), "DL")

    def test_operating_suffixes_are_ignored(self) -> None:
        for call in ("YO3ABC/P", "YO3ABC/M", "YO3ABC/QRP", "YO3ABC/MM"):
            self.assertEqual(base_callsign(call), "YO3ABC")

    def test_a_call_area_digit_is_not_a_location_prefix(self) -> None:
        self.assertEqual(base_callsign("W1AW/4"), "W1AW")

    def test_an_empty_callsign_yields_an_empty_result(self) -> None:
        self.assertEqual(base_callsign("  "), "")
        self.assertEqual(base_callsign("/"), "")


class EntityLookupTests(unittest.TestCase):
    def test_common_prefixes_resolve_to_their_entity(self) -> None:
        expected = {
            "YO3ABC": "România",
            "HA8TKS": "Ungaria",
            "DL1XYZ": "Germania",
            "K1ABC": "Statele Unite",
            "JA1XYZ": "Japonia",
            "VK3ZZ": "Australia",
            "PY2AA": "Brazilia",
            "9A1AA": "Croația",
        }
        for call, entity in expected.items():
            self.assertEqual(entity_of(call).name, entity, call)

    def test_the_longest_matching_prefix_wins(self) -> None:
        # KH6 must not be read as K, nor EA8 as EA.
        self.assertEqual(entity_of("KH6XX").name, "Hawaii")
        self.assertEqual(entity_of("K6XX").name, "Statele Unite")
        self.assertEqual(entity_of("EA8ABC").name, "Insulele Canare")
        self.assertEqual(entity_of("EA5XX").name, "Spania")

    def test_russian_call_areas_separate_europe_from_asia(self) -> None:
        self.assertEqual(entity_of("UA3LMN").name, "Rusia europeană")
        self.assertEqual(entity_of("RA9XYZ").name, "Rusia asiatică")
        self.assertEqual(entity_of("R0ABC").name, "Rusia asiatică")
        self.assertEqual(entity_of("RA2FA").name, "Kaliningrad")

    def test_an_unlisted_prefix_is_reported_as_unknown_not_guessed(self) -> None:
        self.assertIsNone(find_entity("QQ1QQ"))
        self.assertIsNone(find_entity(""))

    def test_every_entity_has_a_continent_the_filter_knows(self) -> None:
        self.assertIn(entity_of("YO3ABC").continent, known_continents())


class LocatorTests(unittest.TestCase):
    def test_a_locator_in_a_comment_is_found(self) -> None:
        self.assertEqual(find_locator("cq dx KN34bk 599"), "KN34BK")

    def test_ordinary_text_is_not_mistaken_for_a_locator(self) -> None:
        self.assertEqual(find_locator("tnx qso 73"), "")
        self.assertEqual(find_locator(""), "")


class LocateTests(unittest.TestCase):
    def test_a_locator_is_preferred_over_the_entity_centre(self) -> None:
        location = location_of("YO3ABC", comment="cq KN34bk")
        self.assertTrue(location.is_precise)
        self.assertEqual(location.locator, "KN34BK")
        self.assertEqual(location.entity, "România")
        self.assertAlmostEqual(location.latitude, 44.44, delta=0.1)

    def test_an_explicit_locator_beats_one_in_the_comment(self) -> None:
        location = location_of("YO3ABC", comment="KN34bk", locator="JN45")
        self.assertEqual(location.locator, "JN45")

    def test_without_a_locator_the_entity_centre_is_used(self) -> None:
        location = location_of("JA1XYZ")
        self.assertFalse(location.is_precise)
        self.assertEqual(location.source, "prefix")
        self.assertEqual(location.entity, "Japonia")

    def test_an_invalid_locator_falls_back_to_the_prefix(self) -> None:
        location = location_of("YO3ABC", locator="ZZ99")
        self.assertEqual(location.source, "prefix")

    def test_a_locator_still_places_a_station_with_an_unknown_prefix(self) -> None:
        location = location_of("QQ1QQ", comment="KN34bk")
        self.assertTrue(location.is_precise)
        self.assertEqual(location.entity, "Necunoscut")

    def test_an_unknown_prefix_without_a_locator_is_not_placed(self) -> None:
        self.assertIsNone(locate("QQ1QQ"))


class PathTests(unittest.TestCase):
    def test_path_returns_distance_and_bearing_from_the_station(self) -> None:
        distance, bearing = require(path_from(location_of("JA1XYZ"), *SIBIU))
        self.assertAlmostEqual(distance, 8894, delta=50)
        self.assertAlmostEqual(bearing, 48, delta=5)

    def test_no_path_without_a_station_position(self) -> None:
        self.assertIsNone(path_from(location_of("JA1XYZ"), None, None))
