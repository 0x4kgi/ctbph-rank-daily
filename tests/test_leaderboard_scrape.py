"""Regression tests for leaderboard_scrape.py (pure / mockable parts).

Network-touching helpers are tested with Ossapi mocked out; per-score
mapping is tested with fakes. Nested helpers inside get_pp_plays
(sort/dedupe) are intentionally NOT covered here -- they are closures
and can only be characterized after extraction (see notes below).
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import leaderboard_scrape as lb


def _ranking_row(**over):
    base = dict(
        country_rank=5, global_rank=100, pp=123.6, hit_accuracy=98.5,
        play_count=10, play_time=3600, total_score=1_000,
        ranked_score=500, total_hits=200,
    )
    base.update(over)
    grade_counts = SimpleNamespace(ss=1, ssh=2, s=3, sh=4, a=5)
    user = SimpleNamespace(id=111, username="alice")
    return SimpleNamespace(user=user, grade_counts=grade_counts, **base)


def _score(**over):
    stats = SimpleNamespace(count_300=10, count_100=2, count_50=1,
                            count_katu=3, count_miss=0)
    beatmap = SimpleNamespace(id=1, version="Insane",
                              difficulty_rating=5.5)
    beatmapset = SimpleNamespace(id=2, title="Song")
    user = SimpleNamespace(username="alice")
    base = dict(
        id=123456789, mods="HD", pp=100.0, rank="S",
        user_id=111, _user=user, beatmapset=beatmapset, beatmap=beatmap,
        perfect=True, max_combo=500, statistics=stats, accuracy=0.98,
    )
    base.update(over)
    ns = SimpleNamespace(**base)
    # allow attribute spelled as _user (SimpleNamespace handles it)
    return ns


class TestEncodeToMap(unittest.TestCase):
    def test_splits_key_from_values_in_order(self):
        mapping = ["a", "b"]
        data = {"id": 7, "a": 1, "b": 2}
        key, values = lb.encode_to_map(mapping, data, "id")
        self.assertEqual(key, 7)
        self.assertEqual(values, [1, 2])


class TestFormatDataFromRows(unittest.TestCase):
    def test_maps_fields(self):
        rows = SimpleNamespace(ranking=[_ranking_row()])
        out = lb.format_data_from_rows(rows)
        self.assertEqual(len(out), 1)
        row = out[0]
        self.assertEqual(row["id"], 111)
        self.assertEqual(row["ign"], "alice")
        self.assertEqual(row["pp"], 124)  # round(123.6)
        self.assertEqual(row["rank_x"], 3)  # ss + ssh
        self.assertEqual(row["rank_s"], 7)  # s + sh
        self.assertEqual(row["rank_a"], 5)


class TestGetPageRankings(unittest.TestCase):
    def test_returns_empty_after_retries(self):
        with patch.object(lb, "Ossapi") as mock_api_cls, \
             patch.object(lb.time, "sleep", return_value=None):
            mock_api_cls.return_value.ranking.side_effect = RuntimeError("boom")
            out = lb.get_page_rankings(page=1, mode="fruits", country="PH")
            self.assertEqual(out, [])
            self.assertEqual(
                mock_api_cls.return_value.ranking.call_count, 3)

    def test_success_maps_rows(self):
        fake_data = SimpleNamespace(ranking=[_ranking_row()])
        with patch.object(lb, "Ossapi") as mock_api_cls:
            mock_api_cls.return_value.ranking.return_value = fake_data
            out = lb.get_page_rankings(page=1, mode="fruits", country="PH")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["ign"], "alice")


class TestGetRankings(unittest.TestCase):
    def test_pages_capped_at_200(self):
        calls = []

        def fake_page(page, mode, country):
            calls.append(page)
            return [{"id": page, "country_rank": page, "global_rank": page,
                     "ign": f"u{page}", "pp": 1, "acc": 1.0, "play_count": 1,
                     "rank_x": 0, "rank_s": 0, "rank_a": 0, "play_time": 0,
                     "total_score": 0, "ranked_score": 0, "total_hits": 0}]

        with patch.object(lb, "get_page_rankings", side_effect=fake_page):
            data = lb.get_rankings(mode="fruits", country="PH", pages=500)
        self.assertEqual(data["pages"], 200)
        self.assertEqual(len(calls), 200)
        self.assertEqual(len(data["data"]), 200)

    def test_empty_pages_skipped(self):
        with patch.object(lb, "get_page_rankings", return_value=[]):
            data = lb.get_rankings(mode="fruits", country="PH", pages=2)
        self.assertEqual(data["data"], {})


class TestDumpToFile(unittest.TestCase):
    def _collection(self, **over):
        base = dict(
            file_version=1.01, update_date=1.0, mode="fruits",
            country="PH", pages=1, map=["ign"], key="id", data={},
        )
        base.update(over)
        return base

    def test_rankings_path_has_no_type_suffix_current_behavior(self):
        # get_rankings() writes 'file_type', but dump_to_file() reads
        # 'type' -- so ranking files take the no-suffix branch. Locked.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                out = lb.dump_to_file(self._collection(), test=True)
            finally:
                os.chdir(cwd)
            self.assertTrue(out.startswith("tests/docs/data/"))
            self.assertTrue(out.endswith("PH-fruits.json"))
            with open(os.path.join(tmp, out)) as f:
                self.assertEqual(json.load(f)["country"], "PH")

    def test_type_suffix_branch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                out = lb.dump_to_file(
                    self._collection(type="pp-records"), test=True)
            finally:
                os.chdir(cwd)
            self.assertTrue(out.endswith("PH-fruits-pp-records.json"))

    def test_production_path_has_no_tests_prefix(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                out = lb.dump_to_file(self._collection(), test=False)
            finally:
                os.chdir(cwd)
            self.assertFalse(out.startswith("tests/"))
            self.assertTrue(out.startswith("docs/data/"))


class TestFormatScoreData(unittest.TestCase):
    def test_empty_in_empty_out(self):
        self.assertEqual(lb.format_score_data_from_list([]), [])

    def test_short_id_is_old_long_is_new(self):
        out = lb.format_score_data_from_list(
            [_score(id=123), _score(id=12345678901)])
        self.assertEqual(out[0]["score_type"], "old")
        self.assertEqual(out[1]["score_type"], "new")

    def test_grade_split_and_fields(self):
        out = lb.format_score_data_from_list([_score(rank="Grade.S")])
        self.assertEqual(out[0]["score_grade"], "S")
        self.assertEqual(out[0]["user_name"], "alice")
        self.assertEqual(out[0]["beatmapset_title"], "Song")
        self.assertEqual(out[0]["count_droplet_miss"], 3)


if __name__ == "__main__":
    unittest.main()
