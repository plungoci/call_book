"""Tests for the great-circle helpers used by the DX cluster panel."""

from __future__ import annotations

import unittest

from call_book.utils.geo import (
    EARTH_RADIUS_KM,
    bearing_degrees,
    cardinal_point,
    distance_km,
    format_bearing,
    format_distance_km,
)

# Sibiu, Budapest and Tokyo: one short path, one long one, both with
# independently known distances to check the formula against.
SIBIU = (45.79, 24.15)
BUDAPEST = (47.50, 19.04)
TOKYO = (35.68, 139.69)


class DistanceTests(unittest.TestCase):
    def test_distance_to_the_same_point_is_zero(self) -> None:
        self.assertAlmostEqual(distance_km(*SIBIU, *SIBIU), 0.0)

    def test_short_path_matches_the_known_distance(self) -> None:
        self.assertAlmostEqual(distance_km(*SIBIU, *BUDAPEST), 434, delta=5)

    def test_long_path_matches_the_known_distance(self) -> None:
        self.assertAlmostEqual(distance_km(*SIBIU, *TOKYO), 8894, delta=30)

    def test_antipodes_are_half_the_circumference_apart(self) -> None:
        self.assertAlmostEqual(distance_km(0, 0, 0, 180), 3.141592653589793 * EARTH_RADIUS_KM, delta=1)

    def test_distance_is_symmetric(self) -> None:
        self.assertAlmostEqual(distance_km(*SIBIU, *TOKYO), distance_km(*TOKYO, *SIBIU), places=6)


class BearingTests(unittest.TestCase):
    def test_due_east_and_due_north(self) -> None:
        self.assertAlmostEqual(bearing_degrees(0, 0, 0, 10), 90.0, places=6)
        self.assertAlmostEqual(bearing_degrees(0, 0, 10, 0), 0.0, places=6)

    def test_bearing_stays_within_a_full_circle(self) -> None:
        for target in (BUDAPEST, TOKYO, (-33.87, 151.21)):
            self.assertTrue(0 <= bearing_degrees(*SIBIU, *target) < 360)

    def test_short_path_to_japan_points_north_east(self) -> None:
        # The well-known heading from central Europe to Japan.
        self.assertAlmostEqual(bearing_degrees(*SIBIU, *TOKYO), 48, delta=5)


class FormattingTests(unittest.TestCase):
    def test_cardinal_points_use_romanian_abbreviations(self) -> None:
        self.assertEqual(cardinal_point(0), "N")
        self.assertEqual(cardinal_point(90), "E")
        self.assertEqual(cardinal_point(180), "S")
        self.assertEqual(cardinal_point(270), "V")
        self.assertEqual(cardinal_point(315), "NV")

    def test_cardinal_point_wraps_around(self) -> None:
        self.assertEqual(cardinal_point(359.9), "N")
        self.assertEqual(cardinal_point(360), "N")

    def test_distances_are_formatted_by_magnitude(self) -> None:
        self.assertEqual(format_distance_km(0.4), "400 m")
        self.assertEqual(format_distance_km(12.34), "12.3 km")
        self.assertEqual(format_distance_km(8894.1), "8 894 km")

    def test_bearing_shows_degrees_and_direction(self) -> None:
        self.assertEqual(format_bearing(48.2), "48° NE")
