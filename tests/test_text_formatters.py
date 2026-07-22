"""Unit tests for reusable live-entry text formatters."""
from __future__ import annotations

import unittest

from utils.text_formatters import format_callsign, format_operator_name


class TextFormatterTests(unittest.TestCase):
    def test_format_callsign_uppercases_letters_only(self):
        self.assertEqual(format_callsign("yo8abc"), "YO8ABC")
        self.assertEqual(format_callsign("yr5d/p"), "YR5D/P")
        self.assertEqual(format_callsign("yo8abc/mm"), "YO8ABC/MM")
        self.assertEqual(format_callsign("yo-8abc/p"), "YO-8ABC/P")

    def test_format_operator_name_uses_title_case(self):
        cases = {
            "ion": "Ion",
            "ION POPESCU": "Ion Popescu",
            "iOn pOpEsCu": "Ion Popescu",
            "marin-ion": "Marin-Ion",
            "o'connor": "O'Connor",
            "ștefan păun": "Ștefan Păun",
        }
        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(format_operator_name(raw_value), expected)

    def test_format_operator_name_preserves_whitespace_and_diacritics(self):
        self.assertEqual(format_operator_name("  ion  păun "), "  Ion  Păun ")


if __name__ == "__main__":
    unittest.main()
