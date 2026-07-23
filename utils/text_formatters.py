"""Presentation-safe text formatters shared by editable user-interface fields."""
from __future__ import annotations


def format_callsign(value: str) -> str:
    """Return a callsign with letters capitalized without changing its structure."""
    return value.upper()


def format_grid_square(value: str) -> str:
    """Return a Maidenhead grid square with letters capitalized."""
    return value.upper()


def format_operator_name(value: str) -> str:
    """Return an operator name in title case while preserving all whitespace."""
    return value.title()
