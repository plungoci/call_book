"""Local conversion between WGS-84 coordinates and Maidenhead locators."""
from __future__ import annotations

def _validate(latitude: float, longitude: float) -> None:
    if not -90 <= latitude <= 90:
        raise ValueError("Latitudinea trebuie să fie între -90 și 90.")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitudinea trebuie să fie între -180 și 180.")


def coordinates_to_maidenhead(latitude: float, longitude: float, precision: int = 6) -> str:
    """Return a 4, 6, or 8 character locator (subsquare letters are lowercase).

    Exact north/east boundaries are assigned to the final representable cell,
    avoiding an out-of-range index caused by floating-point rounding.
    """
    if precision not in (4, 6, 8):
        raise ValueError("Precizia locatorului trebuie să fie 4, 6 sau 8 caractere.")
    _validate(latitude, longitude)
    lat = max(0.0, min(float(latitude) + 90.0, 180.0 - 1e-12))
    lon = max(0.0, min(float(longitude) + 180.0, 360.0 - 1e-12))
    field_lon, field_lat = int(lon // 20), int(lat // 10)
    result = chr(65 + field_lon) + chr(65 + field_lat)
    lon -= field_lon * 20; lat -= field_lat * 10
    square_lon, square_lat = int(lon // 2), int(lat // 1)
    result += f"{square_lon}{square_lat}"
    if precision == 4: return result
    lon -= square_lon * 2; lat -= square_lat
    sub_lon, sub_lat = min(23, int(lon / (2 / 24))), min(23, int(lat / (1 / 24)))
    result += chr(97 + sub_lon) + chr(97 + sub_lat)
    if precision == 6: return result
    lon -= sub_lon * (2 / 24); lat -= sub_lat * (1 / 24)
    result += f"{min(9, int(lon / (2 / 240)))}{min(9, int(lat / (1 / 240)))}"
    return result


def maidenhead_to_coordinates(locator: str) -> tuple[float, float]:
    """Return the latitude/longitude at the centre of a valid Maidenhead cell."""
    text = locator.strip()
    if len(text) not in (4, 6, 8) or not text[:2].isalpha() or not text[2:4].isdigit():
        raise ValueError("Locator Maidenhead invalid.")
    text = text.upper()
    if not ("A" <= text[0] <= "R" and "A" <= text[1] <= "R"):
        raise ValueError("Locator Maidenhead invalid.")
    lon = (ord(text[0]) - 65) * 20.0 - 180; lat = (ord(text[1]) - 65) * 10.0 - 90
    lon += int(text[2]) * 2; lat += int(text[3]); lon_size, lat_size = 2.0, 1.0
    if len(text) >= 6:
        if not ("A" <= text[4] <= "X" and "A" <= text[5] <= "X"): raise ValueError("Locator Maidenhead invalid.")
        lon_size, lat_size = 2 / 24, 1 / 24
        lon += (ord(text[4]) - 65) * lon_size; lat += (ord(text[5]) - 65) * lat_size
    if len(text) == 8:
        if not text[6:].isdigit(): raise ValueError("Locator Maidenhead invalid.")
        lon_size, lat_size = (2 / 24) / 10, (1 / 24) / 10
        lon += int(text[6]) * lon_size; lat += int(text[7]) * lat_size
    return lat + lat_size / 2, lon + lon_size / 2
