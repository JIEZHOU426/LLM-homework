"""Clock tools: leap-year rule boundaries and real date output."""

from __future__ import annotations

import json
import unittest

from core.tools.clock import build_clock_tools
from core.tools.registry import ToolRegistry


class LeapYearTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry(build_clock_tools())

    def call(self, year: int) -> dict:
        raw = self.registry.execute("isleapyear", json.dumps({"year": year}))
        return json.loads(raw)

    def test_divisible_by_four_is_leap(self) -> None:
        self.assertTrue(self.call(2024)["isLeapYear"])

    def test_plain_century_is_not_leap(self) -> None:
        # 1900 能被 4 整除，但整百年必须再被 400 整除
        self.assertFalse(self.call(1900)["isLeapYear"])

    def test_century_divisible_by_400_is_leap(self) -> None:
        self.assertTrue(self.call(2000)["isLeapYear"])

    def test_common_year_is_not_leap(self) -> None:
        self.assertFalse(self.call(2023)["isLeapYear"])

    def test_bad_argument_returns_error_json(self) -> None:
        result = json.loads(
            self.registry.execute("isleapyear", json.dumps({"year": "abc"}))
        )
        self.assertIn("error", result)

    def test_get_current_date_returns_string(self) -> None:
        result = json.loads(self.registry.execute("getDate", "{}"))
        self.assertIn("datetime", result)
        self.assertTrue(str(result["datetime"]))


if __name__ == "__main__":
    unittest.main()
