"""Regression tests for scripts/general_utils.py.

Characterization style: these lock in CURRENT behavior so refactors
don't silently change output. Known quirks are marked explicitly.
"""
import unittest

from scripts.general_utils import (
    format_duration,
    get_pp_pb_place_from_weight,
    simplify_number,
    timestamp_utc_offset,
)


class TestSimplifyNumber(unittest.TestCase):
    def test_small_numbers_have_no_suffix(self):
        self.assertEqual(simplify_number(0), "0")
        self.assertEqual(simplify_number(5), "5")
        self.assertEqual(simplify_number(999), "999")

    def test_thousands(self):
        self.assertEqual(simplify_number(1000), "1.00k")
        self.assertEqual(simplify_number(1500), "1.50k")

    def test_millions_billons(self):
        self.assertEqual(simplify_number(1_500_000), "1.50M")
        self.assertEqual(simplify_number(2_000_000_000), "2.00B")

    def test_used_in_webhook_totals(self):
        # ranked_score totals go through this; lock the format
        self.assertEqual(simplify_number(12_345_678), "12.35M")


class TestTimestampUtcOffset(unittest.TestCase):
    def test_known_conversion(self):
        # 2024-01-01 00:00:00 UTC + 8h (Manila) -> 08:00
        ts = 1704067200.0
        self.assertEqual(
            timestamp_utc_offset(ts, 8, "%Y-%m-%d %H:%M"),
            "2024-01-01 08:00",
        )

    def test_zero_offset_is_utc(self):
        ts = 1704067200.0
        self.assertEqual(
            timestamp_utc_offset(ts, 0, "%Y-%m-%d %H:%M"),
            "2024-01-01 00:00",
        )


class TestGetPpPbPlace(unittest.TestCase):
    def test_full_weight_is_first_place(self):
        self.assertEqual(get_pp_pb_place_from_weight(100), 1)

    def test_95_weight_is_second(self):
        # 100 * 0.95^1 = 95 -> 2nd place in weighted list
        self.assertEqual(get_pp_pb_place_from_weight(95), 2)


class TestFormatDuration(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(format_duration(0), "0s")

    def test_minutes_and_seconds(self):
        self.assertEqual(format_duration(90), "1m 30s")

    def test_hours(self):
        self.assertEqual(format_duration(3661), "1h 1m 1s")

    def test_days(self):
        self.assertEqual(format_duration(90061), "1d 1h 1m 1s")


if __name__ == "__main__":
    unittest.main()
