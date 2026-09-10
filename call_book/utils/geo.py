"""Great-circle helpers shared by the DX cluster and locator features.

Distances use the mean Earth radius (spherical model): accurate to roughly
0.5% versus the WGS-84 ellipsoid, which is far below the precision of the
positions themselves — a DXCC entity centre or a Maidenhead square is only
good to tens of kilometres anyway.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088

_CARDINAL_POINTS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSV", "SV", "VSV", "V", "VNV", "NV", "NNV")


def distance_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """Return the great-circle distance in kilometres between two positions."""
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(haversine)))


def bearing_degrees(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """Return the initial great-circle bearing from A to B, in degrees from true north.

    This is the short-path heading an antenna is pointed at when the QSO
    starts; it changes along the path, so it is not the final bearing.
    """
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lon = math.radians(longitude_b - longitude_a)
    y = math.sin(delta_lon) * math.cos(lat_b)
    x = math.cos(lat_a) * math.sin(lat_b) - math.sin(lat_a) * math.cos(lat_b) * math.cos(delta_lon)
    return math.degrees(math.atan2(y, x)) % 360


def cardinal_point(bearing: float) -> str:
    """Return the 16-point Romanian compass abbreviation for a bearing."""
    index = int((bearing % 360) / 22.5 + 0.5) % len(_CARDINAL_POINTS)
    return _CARDINAL_POINTS[index]


def format_distance_km(distance: float) -> str:
    """Format a distance the way it is read on air: metres below 1 km, then km."""
    if distance < 1:
        return f"{distance * 1000:.0f} m"
    if distance < 100:
        return f"{distance:.1f} km"
    return f"{distance:,.0f} km".replace(",", " ")


def format_bearing(bearing: float) -> str:
    return f"{bearing:.0f}° {cardinal_point(bearing)}"
