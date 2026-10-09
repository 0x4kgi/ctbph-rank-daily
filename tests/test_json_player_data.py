"""Regression tests for scripts/json_player_data.py.

Locks in the map/encode round-trip, diffing semantics (incl. the rank
negation), sorting/filtering, and the comparison-loader wiring.
"""
import unittest
from datetime import datetime
from unittest.mock import patch

from scripts.json_player_data import (
    compare_player_data,
    get_comparison_and_mapped_data,
    get_sorted_dict_on_stat,
    map_player_data,
    sort_data_dictionary,
)


def _raw_collection():
    return {
        "file_version": 1.01,
        "update_date": 1234.0,
        "mode": "fruits",
        "country": "PH",
        "map": ["country_rank", "ign", "pp", "play_count"],
        "key": "id",
        "data": {
            "1": [5, "alice", 100, 10],
            "2": [3, "bob", 200, 20],
        },
    }


class TestMapPlayerData(unittest.TestCase):
    def test_maps_by_position(self):
        mapped = map_player_data(_raw_collection())
        self.assertEqual(mapped["1"], {
            "country_rank": 5, "ign": "alice", "pp": 100, "play_count": 10,
        })
        self.assertEqual(mapped["2"]["ign"], "bob")

    def test_round_trip_with_encode(self):
        # leaderboard_scrape.encode_to_map is the inverse operation
        from leaderboard_scrape import encode_to_map
        raw = _raw_collection()
        mapped = map_player_data(raw)
        for uid, values in raw["data"].items():
            row = dict(zip(raw["map"], values))
            row["id"] = int(uid)
            key, out = encode_to_map(raw["map"], row, "id")
            self.assertEqual(key, int(uid))
            self.assertEqual(list(out), values)


class TestComparePlayerData(unittest.TestCase):
    def _pair(self):
        today = {
            "1": {"ign": "alice", "pp": 150, "play_count": 12,
                  "country_rank": 3, "global_rank": 100},
            "9": {"ign": "newbie", "pp": 10, "play_count": 1,
                  "country_rank": 900, "global_rank": 50000},
        }
        yesterday = {
            "1": {"ign": "alice", "pp": 100, "play_count": 10,
                  "country_rank": 5, "global_rank": 100},
        }
        return today, yesterday

    def test_diffs_subtracted(self):
        today, yesterday = self._pair()
        diff = compare_player_data(today, yesterday)
        self.assertEqual(diff["1"]["pp"], 50)
        self.assertEqual(diff["1"]["play_count"], 2)

    def test_ranks_negated_so_climbing_is_positive(self):
        # alice went PH5 -> PH3 (climbed 2). Stored diff must be +2.
        today, yesterday = self._pair()
        diff = compare_player_data(today, yesterday)
        self.assertEqual(diff["1"]["country_rank"], 2)
        self.assertEqual(diff["1"]["global_rank"], 0)

    def test_new_entry_flagged_and_zeroed(self):
        today, yesterday = self._pair()
        diff = compare_player_data(today, yesterday)
        self.assertTrue(diff["9"]["new_entry"])
        self.assertFalse(diff["1"]["new_entry"])
        self.assertEqual(diff["9"]["ign"], "newbie")
        self.assertEqual(diff["9"]["pp"], 0)

    def test_leavers_are_dropped_current_behavior(self):
        # players present yesterday but gone today are simply absent
        # from the diff (no negative tracking). Locked in so a future
        # change to track leavers is a conscious decision.
        today = {"1": {"ign": "a", "pp": 1}}
        yesterday = {
            "1": {"ign": "a", "pp": 1},
            "2": {"ign": "gone", "pp": 5},
        }
        diff = compare_player_data(today, yesterday)
        self.assertNotIn("2", diff)


class TestSorting(unittest.TestCase):
    def test_sort_highest_first(self):
        data = {"a": {"pp": 1}, "b": {"pp": 5}, "c": {"pp": 3}}
        out = sort_data_dictionary(data, "pp", highest_first=True)
        self.assertEqual(list(out.keys()), ["b", "c", "a"])

    def test_sort_lowest_first_default(self):
        data = {"a": {"pp": 1}, "b": {"pp": 5}}
        out = sort_data_dictionary(data, "pp")
        self.assertEqual(list(out.keys()), ["a", "b"])

    def test_sorted_dict_filters_zeros(self):
        data = {"a": {"pp": 0}, "b": {"pp": 5}, "c": {"pp": 0}}
        out = get_sorted_dict_on_stat(data, "pp", True)
        self.assertEqual(list(out.keys()), ["b"])

    def test_missing_stat_treated_as_zero(self):
        data = {"a": {}, "b": {"pp": 2}}
        out = get_sorted_dict_on_stat(data, "pp", True)
        self.assertEqual(list(out.keys()), ["b"])


class TestGetComparisonAndMappedData(unittest.TestCase):
    def _raw(self, pp, ts):
        return {
            "update_date": ts, "mode": "fruits", "country": "PH",
            "map": ["ign", "pp"], "key": "id",
            "data": {"1": ["alice", pp]},
        }

    def test_happy_path(self):
        latest = self._raw(150, 2000.0)
        comp = self._raw(100, 1000.0)
        with patch(
            "scripts.json_player_data.get_data_at_date",
            side_effect=[latest, comp],
        ):
            res = get_comparison_and_mapped_data(
                base_date=datetime(2024, 6, 10),
                compare_date_offset=1,
                country="PH", mode="fruits", test=True,
            )
        self.assertEqual(res.latest_mapped_data["1"]["pp"], 150)
        self.assertEqual(res.comparison_mapped_data["1"]["pp"], 100)
        self.assertEqual(res.data_difference["1"]["pp"], 50)
        self.assertEqual(res.latest_data_timestamp, 2000.0)
        self.assertEqual(res.comparison_data_timestamp, 1000.0)

    def test_missing_latest_gives_nones(self):
        with patch(
            "scripts.json_player_data.get_data_at_date",
            side_effect=[None, None],
        ):
            res = get_comparison_and_mapped_data(
                base_date=datetime(2024, 6, 10),
                compare_date_offset=1,
                country="PH", mode="fruits", test=True,
            )
        self.assertIsNone(res.latest_mapped_data)
        self.assertIsNone(res.comparison_mapped_data)
        self.assertIsNone(res.data_difference)


if __name__ == "__main__":
    unittest.main()
