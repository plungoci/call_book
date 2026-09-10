"""Approximate geolocation of a callsign, from its DXCC prefix or a locator.

This is the same idea as the public "ham geocoding" DX cluster maps: a spot
carries a callsign, sometimes a Maidenhead locator in its comment, and both
are turned into a position so distance and beam heading can be shown.

Accuracy, stated plainly:

  * A locator is used whenever one is available — it is the operator's own
    position, good to a few kilometres.
  * Otherwise the position is the **centre of the DXCC entity** (in practice
    its capital), so it says "this station is in Japan", not where in Japan.
    For a country the size of the US or Russia the error is thousands of
    kilometres; the distance and bearing shown for such a spot are a rough
    indication, never a beam heading to trust blindly.
  * The prefix table below covers the entities that appear on the cluster in
    everyday use, not all ~340 DXCC entities. An unknown prefix yields
    ``None`` rather than a guess — no location is better than a wrong one.

The table is static: no cty.dat download, no network call, nothing to keep
in sync at runtime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..utils.geo import bearing_degrees, distance_km
from ..utils.maidenhead import maidenhead_to_coordinates

# A locator anywhere in a spot comment ("JN45", "KN05os"), as a whole word so
# ordinary words and signal reports are not mistaken for one.
_GRID_IN_TEXT_RE = re.compile(r"\b([A-R]{2}[0-9]{2}(?:[A-X]{2})?)\b", re.IGNORECASE)

# Callsign suffixes that say how a station operates, not from where.
_OPERATING_SUFFIXES = frozenset(
    {"P", "M", "MM", "AM", "QRP", "QRPP", "A", "B", "LH", "LGT", "BCN", "R", "J", "N", "T", "Y"}
)


@dataclass(frozen=True, slots=True)
class DxccEntity:
    """A DXCC entity with a representative position (its capital or centre)."""

    name: str
    continent: str
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class CallsignLocation:
    """Where a callsign was placed, and how confident that placement is."""

    latitude: float
    longitude: float
    entity: str
    continent: str
    # "locator" when it came from a Maidenhead square in the spot, else
    # "prefix" for the DXCC entity centre.
    source: str
    locator: str = ""

    @property
    def is_precise(self) -> bool:
        return self.source == "locator"


def _entity(name: str, continent: str, latitude: float, longitude: float) -> DxccEntity:
    return DxccEntity(name, continent, latitude, longitude)


# Prefix -> entity. Longest matching prefix wins, so "KH6" beats "K" and
# "EA8" beats "EA"; authoring order here does not matter.
_PREFIX_ENTITIES: dict[str, DxccEntity] = {
    # --- Europa ---
    "YO": _entity("România", "EU", 44.43, 26.10),
    "YP": _entity("România", "EU", 44.43, 26.10),
    "YQ": _entity("România", "EU", 44.43, 26.10),
    "YR": _entity("România", "EU", 44.43, 26.10),
    "HA": _entity("Ungaria", "EU", 47.50, 19.04),
    "HG": _entity("Ungaria", "EU", 47.50, 19.04),
    "OK": _entity("Cehia", "EU", 50.09, 14.42),
    "OL": _entity("Cehia", "EU", 50.09, 14.42),
    "OM": _entity("Slovacia", "EU", 48.15, 17.11),
    "SP": _entity("Polonia", "EU", 52.23, 21.01),
    "SN": _entity("Polonia", "EU", 52.23, 21.01),
    "SQ": _entity("Polonia", "EU", 52.23, 21.01),
    "DL": _entity("Germania", "EU", 52.52, 13.41),
    "DA": _entity("Germania", "EU", 52.52, 13.41),
    "DB": _entity("Germania", "EU", 52.52, 13.41),
    "DC": _entity("Germania", "EU", 52.52, 13.41),
    "DD": _entity("Germania", "EU", 52.52, 13.41),
    "DF": _entity("Germania", "EU", 52.52, 13.41),
    "DG": _entity("Germania", "EU", 52.52, 13.41),
    "DH": _entity("Germania", "EU", 52.52, 13.41),
    "DJ": _entity("Germania", "EU", 52.52, 13.41),
    "DK": _entity("Germania", "EU", 52.52, 13.41),
    "DM": _entity("Germania", "EU", 52.52, 13.41),
    "DO": _entity("Germania", "EU", 52.52, 13.41),
    "DP": _entity("Germania", "EU", 52.52, 13.41),
    "DR": _entity("Germania", "EU", 52.52, 13.41),
    "OE": _entity("Austria", "EU", 48.21, 16.37),
    "HB0": _entity("Liechtenstein", "EU", 47.14, 9.52),
    "HB": _entity("Elveția", "EU", 46.95, 7.45),
    "F": _entity("Franța", "EU", 48.86, 2.35),
    "TM": _entity("Franța", "EU", 48.86, 2.35),
    "TK": _entity("Corsica", "EU", 41.93, 8.74),
    "ON": _entity("Belgia", "EU", 50.85, 4.35),
    "OO": _entity("Belgia", "EU", 50.85, 4.35),
    "OT": _entity("Belgia", "EU", 50.85, 4.35),
    "PA": _entity("Olanda", "EU", 52.37, 4.90),
    "PB": _entity("Olanda", "EU", 52.37, 4.90),
    "PC": _entity("Olanda", "EU", 52.37, 4.90),
    "PD": _entity("Olanda", "EU", 52.37, 4.90),
    "PE": _entity("Olanda", "EU", 52.37, 4.90),
    "PF": _entity("Olanda", "EU", 52.37, 4.90),
    "PG": _entity("Olanda", "EU", 52.37, 4.90),
    "PH": _entity("Olanda", "EU", 52.37, 4.90),
    "PI": _entity("Olanda", "EU", 52.37, 4.90),
    "LX": _entity("Luxemburg", "EU", 49.61, 6.13),
    "G": _entity("Anglia", "EU", 51.51, -0.13),
    "M": _entity("Anglia", "EU", 51.51, -0.13),
    "2E": _entity("Anglia", "EU", 51.51, -0.13),
    "GM": _entity("Scoția", "EU", 55.95, -3.19),
    "MM": _entity("Scoția", "EU", 55.95, -3.19),
    "GW": _entity("Țara Galilor", "EU", 51.48, -3.18),
    "MW": _entity("Țara Galilor", "EU", 51.48, -3.18),
    "GI": _entity("Irlanda de Nord", "EU", 54.60, -5.93),
    "MI": _entity("Irlanda de Nord", "EU", 54.60, -5.93),
    "GD": _entity("Insula Man", "EU", 54.15, -4.48),
    "GJ": _entity("Jersey", "EU", 49.19, -2.11),
    "GU": _entity("Guernsey", "EU", 49.45, -2.58),
    "EI": _entity("Irlanda", "EU", 53.35, -6.26),
    "EJ": _entity("Irlanda", "EU", 53.35, -6.26),
    "I": _entity("Italia", "EU", 41.90, 12.50),
    "IS0": _entity("Sardinia", "EU", 39.22, 9.12),
    "IM0": _entity("Sardinia", "EU", 39.22, 9.12),
    "EA6": _entity("Insulele Baleare", "EU", 39.57, 2.65),
    "EA8": _entity("Insulele Canare", "AF", 28.10, -15.41),
    "EA9": _entity("Ceuta și Melilla", "AF", 35.89, -5.32),
    "EA": _entity("Spania", "EU", 40.42, -3.70),
    "EB": _entity("Spania", "EU", 40.42, -3.70),
    "EC": _entity("Spania", "EU", 40.42, -3.70),
    "ED": _entity("Spania", "EU", 40.42, -3.70),
    "EE": _entity("Spania", "EU", 40.42, -3.70),
    "EF": _entity("Spania", "EU", 40.42, -3.70),
    "EG": _entity("Spania", "EU", 40.42, -3.70),
    "EH": _entity("Spania", "EU", 40.42, -3.70),
    "CT3": _entity("Madeira", "AF", 32.65, -16.91),
    "CQ3": _entity("Madeira", "AF", 32.65, -16.91),
    "CR3": _entity("Madeira", "AF", 32.65, -16.91),
    "CT": _entity("Portugalia", "EU", 38.72, -9.14),
    "CQ": _entity("Portugalia", "EU", 38.72, -9.14),
    "CR": _entity("Portugalia", "EU", 38.72, -9.14),
    "CU": _entity("Azore", "EU", 37.74, -25.67),
    "SM": _entity("Suedia", "EU", 59.33, 18.07),
    "SA": _entity("Suedia", "EU", 59.33, 18.07),
    "SB": _entity("Suedia", "EU", 59.33, 18.07),
    "SC": _entity("Suedia", "EU", 59.33, 18.07),
    "SD": _entity("Suedia", "EU", 59.33, 18.07),
    "SE": _entity("Suedia", "EU", 59.33, 18.07),
    "SF": _entity("Suedia", "EU", 59.33, 18.07),
    "SG": _entity("Suedia", "EU", 59.33, 18.07),
    "SH": _entity("Suedia", "EU", 59.33, 18.07),
    "SI": _entity("Suedia", "EU", 59.33, 18.07),
    "SJ": _entity("Suedia", "EU", 59.33, 18.07),
    "SK": _entity("Suedia", "EU", 59.33, 18.07),
    "SL": _entity("Suedia", "EU", 59.33, 18.07),
    "LA": _entity("Norvegia", "EU", 59.91, 10.75),
    "LB": _entity("Norvegia", "EU", 59.91, 10.75),
    "LC": _entity("Norvegia", "EU", 59.91, 10.75),
    "LG": _entity("Norvegia", "EU", 59.91, 10.75),
    "LI": _entity("Norvegia", "EU", 59.91, 10.75),
    "LJ": _entity("Norvegia", "EU", 59.91, 10.75),
    "LN": _entity("Norvegia", "EU", 59.91, 10.75),
    "JW": _entity("Svalbard", "EU", 78.22, 15.63),
    "JX": _entity("Jan Mayen", "EU", 70.98, -8.53),
    "OZ": _entity("Danemarca", "EU", 55.68, 12.57),
    "OU": _entity("Danemarca", "EU", 55.68, 12.57),
    "OV": _entity("Danemarca", "EU", 55.68, 12.57),
    "5Q": _entity("Danemarca", "EU", 55.68, 12.57),
    "OX": _entity("Groenlanda", "NA", 64.18, -51.72),
    "XP": _entity("Groenlanda", "NA", 64.18, -51.72),
    "OY": _entity("Insulele Feroe", "EU", 62.01, -6.77),
    "TF": _entity("Islanda", "EU", 64.15, -21.94),
    "OH0": _entity("Insulele Åland", "EU", 60.10, 19.93),
    "OJ0": _entity("Market Reef", "EU", 60.30, 19.13),
    "OH": _entity("Finlanda", "EU", 60.17, 24.94),
    "OF": _entity("Finlanda", "EU", 60.17, 24.94),
    "OG": _entity("Finlanda", "EU", 60.17, 24.94),
    "OI": _entity("Finlanda", "EU", 60.17, 24.94),
    "ES": _entity("Estonia", "EU", 59.44, 24.75),
    "YL": _entity("Letonia", "EU", 56.95, 24.11),
    "LY": _entity("Lituania", "EU", 54.69, 25.28),
    "ER": _entity("Moldova", "EU", 47.01, 28.86),
    "UR": _entity("Ucraina", "EU", 50.45, 30.52),
    "US": _entity("Ucraina", "EU", 50.45, 30.52),
    "UT": _entity("Ucraina", "EU", 50.45, 30.52),
    "UU": _entity("Ucraina", "EU", 50.45, 30.52),
    "UV": _entity("Ucraina", "EU", 50.45, 30.52),
    "UW": _entity("Ucraina", "EU", 50.45, 30.52),
    "UX": _entity("Ucraina", "EU", 50.45, 30.52),
    "UY": _entity("Ucraina", "EU", 50.45, 30.52),
    "UZ": _entity("Ucraina", "EU", 50.45, 30.52),
    "EM": _entity("Ucraina", "EU", 50.45, 30.52),
    "EN": _entity("Ucraina", "EU", 50.45, 30.52),
    "EO": _entity("Ucraina", "EU", 50.45, 30.52),
    "EU": _entity("Belarus", "EU", 53.90, 27.57),
    "EV": _entity("Belarus", "EU", 53.90, 27.57),
    "EW": _entity("Belarus", "EU", 53.90, 27.57),
    "LZ": _entity("Bulgaria", "EU", 42.70, 23.32),
    "SV5": _entity("Dodecanez", "EU", 36.44, 28.22),
    "SV9": _entity("Creta", "EU", 35.34, 25.13),
    "SV": _entity("Grecia", "EU", 37.98, 23.73),
    "SW": _entity("Grecia", "EU", 37.98, 23.73),
    "SX": _entity("Grecia", "EU", 37.98, 23.73),
    "SY": _entity("Grecia", "EU", 37.98, 23.73),
    "SZ": _entity("Grecia", "EU", 37.98, 23.73),
    "SJ2": _entity("Muntele Athos", "EU", 40.16, 24.33),
    "9A": _entity("Croația", "EU", 45.81, 15.98),
    "S5": _entity("Slovenia", "EU", 46.06, 14.51),
    "E7": _entity("Bosnia și Herțegovina", "EU", 43.86, 18.41),
    "YU": _entity("Serbia", "EU", 44.79, 20.45),
    "YT": _entity("Serbia", "EU", 44.79, 20.45),
    "4O": _entity("Muntenegru", "EU", 42.44, 19.26),
    "Z6": _entity("Kosovo", "EU", 42.66, 21.16),
    "Z3": _entity("Macedonia de Nord", "EU", 41.99, 21.43),
    "ZA": _entity("Albania", "EU", 41.33, 19.82),
    "9H": _entity("Malta", "EU", 35.90, 14.51),
    "T7": _entity("San Marino", "EU", 43.94, 12.45),
    "HV": _entity("Vatican", "EU", 41.90, 12.45),
    "3A": _entity("Monaco", "EU", 43.73, 7.42),
    "C3": _entity("Andorra", "EU", 42.51, 1.52),
    "5B": _entity("Cipru", "AS", 35.17, 33.36),
    "C4": _entity("Cipru", "AS", 35.17, 33.36),
    "H2": _entity("Cipru", "AS", 35.17, 33.36),
    "ZB2": _entity("Gibraltar", "EU", 36.14, -5.35),
    # --- Rusia și fostul spațiu sovietic (vezi și regulile pe cifră) ---
    "UA": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "UB": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "UC": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "UD": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "UE": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "UF": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "UG": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "UH": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "UI": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "R": _entity("Rusia europeană", "EU", 55.75, 37.62),
    "UN": _entity("Kazahstan", "AS", 51.13, 71.43),
    "UO": _entity("Kazahstan", "AS", 51.13, 71.43),
    "UP": _entity("Kazahstan", "AS", 51.13, 71.43),
    "UQ": _entity("Kazahstan", "AS", 51.13, 71.43),
    "EX": _entity("Kârgâzstan", "AS", 42.87, 74.59),
    "EY": _entity("Tadjikistan", "AS", 38.56, 68.79),
    "EZ": _entity("Turkmenistan", "AS", 37.95, 58.38),
    "UJ": _entity("Uzbekistan", "AS", 41.30, 69.24),
    "UK": _entity("Uzbekistan", "AS", 41.30, 69.24),
    "UM": _entity("Uzbekistan", "AS", 41.30, 69.24),
    "4L": _entity("Georgia", "AS", 41.72, 44.78),
    "4J": _entity("Azerbaidjan", "AS", 40.41, 49.87),
    "4K": _entity("Azerbaidjan", "AS", 40.41, 49.87),
    "EK": _entity("Armenia", "AS", 40.18, 44.51),
    # --- Asia ---
    "JA": _entity("Japonia", "AS", 35.68, 139.69),
    "JE": _entity("Japonia", "AS", 35.68, 139.69),
    "JF": _entity("Japonia", "AS", 35.68, 139.69),
    "JG": _entity("Japonia", "AS", 35.68, 139.69),
    "JH": _entity("Japonia", "AS", 35.68, 139.69),
    "JI": _entity("Japonia", "AS", 35.68, 139.69),
    "JJ": _entity("Japonia", "AS", 35.68, 139.69),
    "JK": _entity("Japonia", "AS", 35.68, 139.69),
    "JL": _entity("Japonia", "AS", 35.68, 139.69),
    "JM": _entity("Japonia", "AS", 35.68, 139.69),
    "JN": _entity("Japonia", "AS", 35.68, 139.69),
    "JO": _entity("Japonia", "AS", 35.68, 139.69),
    "JP": _entity("Japonia", "AS", 35.68, 139.69),
    "JQ": _entity("Japonia", "AS", 35.68, 139.69),
    "JR": _entity("Japonia", "AS", 35.68, 139.69),
    "JS": _entity("Japonia", "AS", 35.68, 139.69),
    "7J": _entity("Japonia", "AS", 35.68, 139.69),
    "8J": _entity("Japonia", "AS", 35.68, 139.69),
    "JD1": _entity("Ogasawara", "AS", 27.09, 142.19),
    "HL": _entity("Coreea de Sud", "AS", 37.57, 126.98),
    "DS": _entity("Coreea de Sud", "AS", 37.57, 126.98),
    "6K": _entity("Coreea de Sud", "AS", 37.57, 126.98),
    "6L": _entity("Coreea de Sud", "AS", 37.57, 126.98),
    "P5": _entity("Coreea de Nord", "AS", 39.02, 125.75),
    "BV": _entity("Taiwan", "AS", 25.03, 121.57),
    "BY": _entity("China", "AS", 39.90, 116.41),
    "BA": _entity("China", "AS", 39.90, 116.41),
    "BD": _entity("China", "AS", 39.90, 116.41),
    "BG": _entity("China", "AS", 39.90, 116.41),
    "BH": _entity("China", "AS", 39.90, 116.41),
    "BI": _entity("China", "AS", 39.90, 116.41),
    "BT": _entity("China", "AS", 39.90, 116.41),
    "VR2": _entity("Hong Kong", "AS", 22.32, 114.17),
    "XX9": _entity("Macao", "AS", 22.20, 113.54),
    "JT": _entity("Mongolia", "AS", 47.89, 106.91),
    "VU": _entity("India", "AS", 28.61, 77.21),
    "AT": _entity("India", "AS", 28.61, 77.21),
    "4S": _entity("Sri Lanka", "AS", 6.93, 79.86),
    "S2": _entity("Bangladesh", "AS", 23.81, 90.41),
    "9N": _entity("Nepal", "AS", 27.72, 85.32),
    "A5": _entity("Bhutan", "AS", 27.47, 89.64),
    "AP": _entity("Pakistan", "AS", 33.68, 73.05),
    "YA": _entity("Afganistan", "AS", 34.53, 69.17),
    "EP": _entity("Iran", "AS", 35.69, 51.39),
    "YI": _entity("Irak", "AS", 33.32, 44.36),
    "YK": _entity("Siria", "AS", 33.51, 36.29),
    "OD": _entity("Liban", "AS", 33.89, 35.50),
    "JY": _entity("Iordania", "AS", 31.95, 35.93),
    "4X": _entity("Israel", "AS", 31.77, 35.21),
    "4Z": _entity("Israel", "AS", 31.77, 35.21),
    "E4": _entity("Palestina", "AS", 31.90, 35.20),
    "TA": _entity("Turcia", "EU", 39.93, 32.86),
    "TB": _entity("Turcia", "EU", 39.93, 32.86),
    "TC": _entity("Turcia", "EU", 39.93, 32.86),
    "HZ": _entity("Arabia Saudită", "AS", 24.71, 46.68),
    "7Z": _entity("Arabia Saudită", "AS", 24.71, 46.68),
    "8Z": _entity("Arabia Saudită", "AS", 24.71, 46.68),
    "9K": _entity("Kuwait", "AS", 29.38, 47.99),
    "A4": _entity("Oman", "AS", 23.59, 58.41),
    "A6": _entity("Emiratele Arabe Unite", "AS", 24.45, 54.38),
    "A7": _entity("Qatar", "AS", 25.29, 51.53),
    "A9": _entity("Bahrain", "AS", 26.23, 50.59),
    "7O": _entity("Yemen", "AS", 15.35, 44.21),
    "XU": _entity("Cambodgia", "AS", 11.56, 104.92),
    "XW": _entity("Laos", "AS", 17.98, 102.63),
    "XV": _entity("Vietnam", "AS", 21.03, 105.85),
    "3W": _entity("Vietnam", "AS", 21.03, 105.85),
    "HS": _entity("Thailanda", "AS", 13.76, 100.50),
    "E2": _entity("Thailanda", "AS", 13.76, 100.50),
    "XZ": _entity("Myanmar", "AS", 16.87, 96.20),
    "9M6": _entity("Malaysia de Est", "OC", 5.98, 116.07),
    "9M8": _entity("Malaysia de Est", "OC", 1.55, 110.35),
    "9M": _entity("Malaysia de Vest", "AS", 3.14, 101.69),
    "9V": _entity("Singapore", "AS", 1.35, 103.82),
    "V8": _entity("Brunei", "OC", 4.90, 114.94),
    "YB": _entity("Indonezia", "OC", -6.21, 106.85),
    "YC": _entity("Indonezia", "OC", -6.21, 106.85),
    "YD": _entity("Indonezia", "OC", -6.21, 106.85),
    "YE": _entity("Indonezia", "OC", -6.21, 106.85),
    "YF": _entity("Indonezia", "OC", -6.21, 106.85),
    "YG": _entity("Indonezia", "OC", -6.21, 106.85),
    "YH": _entity("Indonezia", "OC", -6.21, 106.85),
    "8A": _entity("Indonezia", "OC", -6.21, 106.85),
    "DU": _entity("Filipine", "OC", 14.60, 120.98),
    "DV": _entity("Filipine", "OC", 14.60, 120.98),
    "DW": _entity("Filipine", "OC", 14.60, 120.98),
    "DX": _entity("Filipine", "OC", 14.60, 120.98),
    "DY": _entity("Filipine", "OC", 14.60, 120.98),
    "DZ": _entity("Filipine", "OC", 14.60, 120.98),
    "4W": _entity("Timorul de Est", "OC", -8.56, 125.56),
    # --- America de Nord ---
    "KH6": _entity("Hawaii", "OC", 21.31, -157.86),
    "KH7": _entity("Hawaii", "OC", 21.31, -157.86),
    "KH2": _entity("Guam", "OC", 13.44, 144.79),
    "KH0": _entity("Marianele de Nord", "OC", 15.19, 145.75),
    "KH8": _entity("Samoa Americană", "OC", -14.28, -170.70),
    "KH9": _entity("Insula Wake", "OC", 19.28, 166.65),
    "KL": _entity("Alaska", "NA", 61.22, -149.90),
    "AL": _entity("Alaska", "NA", 61.22, -149.90),
    "NL": _entity("Alaska", "NA", 61.22, -149.90),
    "WL": _entity("Alaska", "NA", 61.22, -149.90),
    "KP4": _entity("Puerto Rico", "NA", 18.47, -66.11),
    "NP4": _entity("Puerto Rico", "NA", 18.47, -66.11),
    "WP4": _entity("Puerto Rico", "NA", 18.47, -66.11),
    "KP2": _entity("Insulele Virgine SUA", "NA", 18.34, -64.93),
    "K": _entity("Statele Unite", "NA", 38.91, -77.04),
    "W": _entity("Statele Unite", "NA", 38.91, -77.04),
    "N": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AA": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AB": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AC": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AD": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AE": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AF": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AG": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AI": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AJ": _entity("Statele Unite", "NA", 38.91, -77.04),
    "AK": _entity("Statele Unite", "NA", 38.91, -77.04),
    "VE": _entity("Canada", "NA", 45.42, -75.70),
    "VA": _entity("Canada", "NA", 45.42, -75.70),
    "VO": _entity("Canada", "NA", 47.56, -52.71),
    "VY": _entity("Canada", "NA", 62.45, -114.37),
    "CY0": _entity("Insula Sable", "NA", 43.93, -60.01),
    "XE": _entity("Mexic", "NA", 19.43, -99.13),
    "XF": _entity("Mexic", "NA", 19.43, -99.13),
    "4A": _entity("Mexic", "NA", 19.43, -99.13),
    "6D": _entity("Mexic", "NA", 19.43, -99.13),
    "CO": _entity("Cuba", "NA", 23.11, -82.37),
    "CM": _entity("Cuba", "NA", 23.11, -82.37),
    "HI": _entity("Republica Dominicană", "NA", 18.49, -69.93),
    "HH": _entity("Haiti", "NA", 18.59, -72.31),
    "6Y": _entity("Jamaica", "NA", 17.97, -76.79),
    "C6": _entity("Bahamas", "NA", 25.05, -77.35),
    "ZF": _entity("Insulele Cayman", "NA", 19.29, -81.38),
    "V3": _entity("Belize", "NA", 17.25, -88.77),
    "TG": _entity("Guatemala", "NA", 14.63, -90.51),
    "YS": _entity("El Salvador", "NA", 13.69, -89.19),
    "HR": _entity("Honduras", "NA", 14.07, -87.19),
    "YN": _entity("Nicaragua", "NA", 12.11, -86.24),
    "TI": _entity("Costa Rica", "NA", 9.93, -84.08),
    "HP": _entity("Panama", "NA", 8.98, -79.52),
    "V4": _entity("Saint Kitts și Nevis", "NA", 17.30, -62.72),
    "V2": _entity("Antigua și Barbuda", "NA", 17.12, -61.85),
    "J3": _entity("Grenada", "NA", 12.05, -61.75),
    "J6": _entity("Saint Lucia", "NA", 14.01, -60.99),
    "J7": _entity("Dominica", "NA", 15.30, -61.39),
    "J8": _entity("Saint Vincent", "NA", 13.16, -61.22),
    "8P": _entity("Barbados", "NA", 13.10, -59.62),
    "9Y": _entity("Trinidad și Tobago", "NA", 10.65, -61.51),
    "PJ2": _entity("Curaçao", "SA", 12.11, -68.93),
    "PJ4": _entity("Bonaire", "SA", 12.15, -68.28),
    "PJ7": _entity("Sint Maarten", "NA", 18.03, -63.05),
    "FM": _entity("Martinica", "NA", 14.60, -61.07),
    "FG": _entity("Guadelupa", "NA", 16.24, -61.53),
    "FS": _entity("Saint Martin", "NA", 18.07, -63.08),
    "FJ": _entity("Saint Barthélemy", "NA", 17.90, -62.83),
    "VP9": _entity("Bermuda", "NA", 32.29, -64.78),
    "VP5": _entity("Turks și Caicos", "NA", 21.46, -71.14),
    "VP2E": _entity("Anguilla", "NA", 18.22, -63.07),
    "VP2M": _entity("Montserrat", "NA", 16.75, -62.21),
    "VP2V": _entity("Insulele Virgine Britanice", "NA", 18.43, -64.62),
    # --- America de Sud ---
    "PY": _entity("Brazilia", "SA", -15.79, -47.88),
    "PP": _entity("Brazilia", "SA", -15.79, -47.88),
    "PQ": _entity("Brazilia", "SA", -15.79, -47.88),
    "PR": _entity("Brazilia", "SA", -15.79, -47.88),
    "PS": _entity("Brazilia", "SA", -15.79, -47.88),
    "PT": _entity("Brazilia", "SA", -15.79, -47.88),
    "PU": _entity("Brazilia", "SA", -15.79, -47.88),
    "PV": _entity("Brazilia", "SA", -15.79, -47.88),
    "PW": _entity("Brazilia", "SA", -15.79, -47.88),
    "ZZ": _entity("Brazilia", "SA", -15.79, -47.88),
    "LU": _entity("Argentina", "SA", -34.60, -58.38),
    "AY": _entity("Argentina", "SA", -34.60, -58.38),
    "AZ": _entity("Argentina", "SA", -34.60, -58.38),
    "CE": _entity("Chile", "SA", -33.45, -70.67),
    "CA": _entity("Chile", "SA", -33.45, -70.67),
    "CB": _entity("Chile", "SA", -33.45, -70.67),
    "XQ": _entity("Chile", "SA", -33.45, -70.67),
    "CX": _entity("Uruguay", "SA", -34.90, -56.19),
    "ZP": _entity("Paraguay", "SA", -25.28, -57.64),
    "CP": _entity("Bolivia", "SA", -16.50, -68.15),
    "OA": _entity("Peru", "SA", -12.05, -77.04),
    "HC8": _entity("Galapagos", "SA", -0.74, -90.31),
    "HC": _entity("Ecuador", "SA", -0.18, -78.47),
    "HD": _entity("Ecuador", "SA", -0.18, -78.47),
    "HK": _entity("Columbia", "SA", 4.71, -74.07),
    "HJ": _entity("Columbia", "SA", 4.71, -74.07),
    "YV": _entity("Venezuela", "SA", 10.48, -66.90),
    "YW": _entity("Venezuela", "SA", 10.48, -66.90),
    "YY": _entity("Venezuela", "SA", 10.48, -66.90),
    "8R": _entity("Guyana", "SA", 6.80, -58.16),
    "PZ": _entity("Surinam", "SA", 5.85, -55.20),
    "FY": _entity("Guyana Franceză", "SA", 4.92, -52.33),
    "VP8": _entity("Insulele Falkland", "SA", -51.70, -57.85),
    "CE0": _entity("Insula Paștelui", "SA", -27.15, -109.43),
    # --- Africa ---
    "CN": _entity("Maroc", "AF", 33.97, -6.85),
    "7X": _entity("Algeria", "AF", 36.75, 3.06),
    "3V": _entity("Tunisia", "AF", 36.81, 10.18),
    "5A": _entity("Libia", "AF", 32.89, 13.19),
    "SU": _entity("Egipt", "AF", 30.04, 31.24),
    "ST": _entity("Sudan", "AF", 15.50, 32.56),
    "Z8": _entity("Sudanul de Sud", "AF", 4.85, 31.58),
    "ET": _entity("Etiopia", "AF", 9.03, 38.74),
    "E3": _entity("Eritreea", "AF", 15.34, 38.93),
    "J2": _entity("Djibouti", "AF", 11.59, 43.15),
    "6O": _entity("Somalia", "AF", 2.04, 45.34),
    "5Z": _entity("Kenya", "AF", -1.29, 36.82),
    "5H": _entity("Tanzania", "AF", -6.79, 39.21),
    "5X": _entity("Uganda", "AF", 0.35, 32.58),
    "9X": _entity("Rwanda", "AF", -1.94, 30.06),
    "9U": _entity("Burundi", "AF", -3.38, 29.36),
    "9Q": _entity("R.D. Congo", "AF", -4.44, 15.27),
    "TN": _entity("Congo", "AF", -4.26, 15.28),
    "TR": _entity("Gabon", "AF", 0.42, 9.47),
    "TJ": _entity("Camerun", "AF", 3.85, 11.50),
    "TL": _entity("Republica Centrafricană", "AF", 4.39, 18.56),
    "TT": _entity("Ciad", "AF", 12.13, 15.06),
    "5U": _entity("Niger", "AF", 13.51, 2.11),
    "5N": _entity("Nigeria", "AF", 9.06, 7.49),
    "9G": _entity("Ghana", "AF", 5.60, -0.19),
    "TU": _entity("Coasta de Fildeș", "AF", 6.83, -5.29),
    "XT": _entity("Burkina Faso", "AF", 12.37, -1.52),
    "5V": _entity("Togo", "AF", 6.17, 1.23),
    "TY": _entity("Benin", "AF", 6.50, 2.62),
    "TZ": _entity("Mali", "AF", 12.64, -8.00),
    "5T": _entity("Mauritania", "AF", 18.08, -15.98),
    "6W": _entity("Senegal", "AF", 14.72, -17.47),
    "C5": _entity("Gambia", "AF", 13.45, -16.58),
    "J5": _entity("Guineea-Bissau", "AF", 11.86, -15.60),
    "3X": _entity("Guineea", "AF", 9.51, -13.71),
    "9L": _entity("Sierra Leone", "AF", 8.48, -13.23),
    "EL": _entity("Liberia", "AF", 6.30, -10.80),
    "D4": _entity("Capul Verde", "AF", 14.93, -23.51),
    "S9": _entity("São Tomé și Príncipe", "AF", 0.34, 6.73),
    "3C": _entity("Guineea Ecuatorială", "AF", 3.75, 8.78),
    "D2": _entity("Angola", "AF", -8.84, 13.23),
    "9J": _entity("Zambia", "AF", -15.39, 28.32),
    "7Q": _entity("Malawi", "AF", -13.96, 33.79),
    "C9": _entity("Mozambic", "AF", -25.97, 32.57),
    "Z2": _entity("Zimbabwe", "AF", -17.83, 31.05),
    "A2": _entity("Botswana", "AF", -24.65, 25.91),
    "V5": _entity("Namibia", "AF", -22.56, 17.08),
    "7P": _entity("Lesotho", "AF", -29.31, 27.48),
    "3DA": _entity("Eswatini", "AF", -26.31, 31.14),
    "ZS": _entity("Africa de Sud", "AF", -25.75, 28.19),
    "ZR": _entity("Africa de Sud", "AF", -25.75, 28.19),
    "ZT": _entity("Africa de Sud", "AF", -25.75, 28.19),
    "ZU": _entity("Africa de Sud", "AF", -25.75, 28.19),
    "5R": _entity("Madagascar", "AF", -18.88, 47.51),
    "S7": _entity("Seychelles", "AF", -4.62, 55.45),
    "3B8": _entity("Mauritius", "AF", -20.16, 57.50),
    "3B9": _entity("Rodrigues", "AF", -19.69, 63.42),
    "3B7": _entity("Saint Brandon", "AF", -16.58, 59.62),
    "FR": _entity("Réunion", "AF", -20.88, 55.45),
    "FH": _entity("Mayotte", "AF", -12.78, 45.23),
    "D6": _entity("Comore", "AF", -11.70, 43.26),
    "ZD7": _entity("Sfânta Elena", "AF", -15.94, -5.72),
    "ZD8": _entity("Insula Ascension", "AF", -7.95, -14.36),
    "ZD9": _entity("Tristan da Cunha", "AF", -37.07, -12.31),
    "9L0": _entity("Sierra Leone", "AF", 8.48, -13.23),
    # --- Oceania ---
    "VK9": _entity("Insulele externe australiene", "OC", -29.04, 167.95),
    "VK0": _entity("Insulele antarctice australiene", "AN", -53.10, 73.52),
    "VK": _entity("Australia", "OC", -35.28, 149.13),
    "AX": _entity("Australia", "OC", -35.28, 149.13),
    "ZL": _entity("Noua Zeelandă", "OC", -41.29, 174.78),
    "ZM": _entity("Noua Zeelandă", "OC", -41.29, 174.78),
    "P2": _entity("Papua Noua Guinee", "OC", -9.44, 147.18),
    "H4": _entity("Insulele Solomon", "OC", -9.43, 159.96),
    "YJ": _entity("Vanuatu", "OC", -17.73, 168.32),
    "FK": _entity("Noua Caledonie", "OC", -22.27, 166.44),
    "3D2": _entity("Fiji", "OC", -18.14, 178.44),
    "5W": _entity("Samoa", "OC", -13.83, -171.77),
    "A3": _entity("Tonga", "OC", -21.14, -175.20),
    "E5": _entity("Insulele Cook", "OC", -21.21, -159.78),
    "FO": _entity("Polinezia Franceză", "OC", -17.54, -149.57),
    "FW": _entity("Wallis și Futuna", "OC", -13.28, -176.18),
    "C2": _entity("Nauru", "OC", -0.55, 166.92),
    "T2": _entity("Tuvalu", "OC", -8.52, 179.20),
    "T3": _entity("Kiribati", "OC", 1.33, 172.98),
    "T8": _entity("Palau", "OC", 7.50, 134.62),
    "V6": _entity("Micronezia", "OC", 6.92, 158.16),
    "V7": _entity("Insulele Marshall", "OC", 7.09, 171.38),
    # --- Antarctica ---
    "KC4": _entity("Antarctica", "AN", -75.10, 123.35),
    "DP0": _entity("Antarctica", "AN", -70.65, -8.25),
    "RI1AN": _entity("Antarctica", "AN", -69.38, 76.38),
    "8J1": _entity("Antarctica", "AN", -69.00, 39.58),
}

# Prefixes whose entity depends on the call area digit. Checked before the
# plain prefix table: in Russia the digit is what separates the European part
# from the Asiatic one, which are different DXCC entities thousands of
# kilometres apart.
_ASIATIC_RUSSIA = _entity("Rusia asiatică", "AS", 55.03, 82.92)
_KALININGRAD = _entity("Kaliningrad", "EU", 54.71, 20.51)
_PATTERN_ENTITIES: tuple[tuple[re.Pattern[str], DxccEntity], ...] = (
    (re.compile(r"^(?:R|U)[A-Z]?2[A-Z]"), _KALININGRAD),
    (re.compile(r"^(?:R|U)[A-Z]?[08-9]"), _ASIATIC_RUSSIA),
)

# Longest first, so "KH6" is tried before "KH" and "K".
_SORTED_PREFIXES: tuple[tuple[str, DxccEntity], ...] = tuple(
    sorted(_PREFIX_ENTITIES.items(), key=lambda item: len(item[0]), reverse=True)
)


def base_callsign(callsign: str) -> str:
    """Return the part of a compound callsign that says where the station is.

    ``DL/YO3ABC/P`` is a Romanian operator in Germany, so "DL" decides;
    ``W1AW/4`` and ``YO3ABC/QRP`` carry no location prefix, so the callsign
    itself decides. Operating suffixes and bare call-area digits are dropped,
    then the shortest remaining part wins — a prefix indicator is always
    shorter than the full callsign it qualifies.
    """
    parts = [part for part in callsign.strip().upper().split("/") if part]
    if not parts:
        return ""
    meaningful = [part for part in parts if part not in _OPERATING_SUFFIXES and not part.isdigit()]
    if not meaningful:
        return parts[0]
    return min(meaningful, key=len)


def find_entity(callsign: str) -> DxccEntity | None:
    """Return the DXCC entity a callsign belongs to, or ``None`` when unlisted."""
    call = base_callsign(callsign)
    if not call:
        return None
    for pattern, entity in _PATTERN_ENTITIES:
        if pattern.match(call):
            return entity
    for prefix, entity in _SORTED_PREFIXES:
        if call.startswith(prefix):
            return entity
    return None


def find_locator(text: str) -> str:
    """Return the first Maidenhead locator written in a spot comment, if any."""
    match = _GRID_IN_TEXT_RE.search(text or "")
    return match.group(1).upper() if match else ""


def locate(callsign: str, comment: str = "", locator: str = "") -> CallsignLocation | None:
    """Place a spotted station, preferring a locator over the entity centre.

    ``locator`` is an explicitly known square (e.g. from the logbook);
    ``comment`` is free text a locator may be mentioned in.
    """
    entity = find_entity(callsign)
    square = (locator or find_locator(comment)).upper()
    if square:
        try:
            latitude, longitude = maidenhead_to_coordinates(square)
        except ValueError:
            square = ""
        else:
            return CallsignLocation(
                latitude,
                longitude,
                entity.name if entity else "Necunoscut",
                entity.continent if entity else "",
                "locator",
                square,
            )
    if entity is None:
        return None
    return CallsignLocation(entity.latitude, entity.longitude, entity.name, entity.continent, "prefix")


def path_from(
    location: CallsignLocation, latitude: float | None, longitude: float | None
) -> tuple[float, float] | None:
    """Return (distance km, bearing degrees) from the station to a spot."""
    if latitude is None or longitude is None:
        return None
    return (
        distance_km(latitude, longitude, location.latitude, location.longitude),
        bearing_degrees(latitude, longitude, location.latitude, location.longitude),
    )


def known_continents() -> tuple[str, ...]:
    """Return the continent codes used by the table, in a stable order."""
    return ("EU", "NA", "SA", "AS", "AF", "OC", "AN")
