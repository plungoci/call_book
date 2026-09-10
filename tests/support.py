"""Small helpers shared by the test suite."""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


def require(value: T | None, message: str = "") -> T:
    """Return a value that must not be ``None``, failing the test if it is.

    Qt's ``QTableWidget.item()`` and the geocoder's lookups are legitimately
    optional at the type level. A test that asks for a cell it has just
    populated wants the value, not the ``None`` branch — this keeps the
    assertion in one place instead of repeating it at every call site.
    """
    assert value is not None, message or "Valoare așteptată, dar lipsă."
    return value
