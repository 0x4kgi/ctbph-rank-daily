"""Regression tests for send_discord_webhook.py (pure / mockable parts)."""
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import send_discord_webhook as w


class TestGradeEmotes(unittest.TestCase):
    def test_all_grades_mapped(self):
        for grade in ["SSH", "SS", "SH", "S", "A", "B", "C", "D"]:
            emote = w.get_emote_for_score_grade(grade)
            self.assertTrue(emote.startswith("<:ranking"),
                            f"{grade} -> {emote}")

    def test_enum_string_form_split(self):
        # code does str(grade).split('.')[-1], so "Grade.S" works too
        self.assertEqual(w.get_emote_for_score_grade("Grade.S"),
                         w.get_emote_for_score_grade("S"))

    def test_unknown_grade_gives_question_mark(self):
        self.assertEqual(w.get_emote_for_score_grade("X"), "?")
        self.assertEqual(w.get_emote_for_score_grade("F"), "?")


class TestMissFormat(unittest.TestCase):
    def test_zero_and_none_are_fc(self):
        self.assertEqual(w.miss_format(0), "**FC 👍**")
        self.assertEqual(w.miss_format(None), "**FC 👍**")

    def test_nonzero_shows_count(self):
        self.assertEqual(w.miss_format(3), "3❌")
        self.assertEqual(w.miss_format(1000), "1,000❌")


class TestGetNewEntries(unittest.TestCase):
    def test_filters_on_flag(self):
        data = {"1": {"new_entry": True, "ign": "a"},
                "2": {"new_entry": False, "ign": "b"}}
        self.assertEqual(list(w.get_new_entries(data).keys()), ["1"])


class TestDescriptionMaker(unittest.TestCase):
    def _data(self):
        active = {"1": {"play_count": 5}, "2": {"play_count": 0}}
        pp = {"1": {"pp": 10}, "2": {"pp": 0}}
        rank = {"1": {"country_rank": 3}, "2": {"country_rank": 0}}
        rs = {"1": {"ranked_score": 1500}, "2": {"ranked_score": 0}}
        return active, pp, rank, rs

    def test_counts_and_totals(self):
        desc = w.description_maker(*self._data())
        self.assertIn("**1** players who played", desc)
        self.assertIn("**1** players who saw pp gains", desc)
        self.assertIn("**10pp**", desc)
        self.assertIn("**3 ranks**", desc)
        self.assertIn("**5 play count**", desc)

    def test_no_template_markers_left(self):
        desc = w.description_maker(*self._data())
        self.assertNotIn("!n", desc)
        self.assertIn("\n", desc)  # hack converts !n to real newlines


class TestPlayerSummaryFields(unittest.TestCase):
    def _inputs(self):
        latest = {"1": {"pp": 150, "country_rank": 3,
                        "play_count": 12, "ranked_score": 6000},
                  "2": {"pp": 50, "country_rank": 10,
                        "play_count": 2, "ranked_score": 100}}
        comp = {"1": {"pp": 100, "country_rank": 5,
                      "play_count": 10, "ranked_score": 5000},
                "2": {"pp": 50, "country_rank": 10,
                      "play_count": 2, "ranked_score": 100}}
        diff = {"1": {"ign": "alice", "pp": 50, "country_rank": 2,
                      "play_count": 2, "ranked_score": 1000},
                "2": {"ign": "bob", "pp": 0, "country_rank": 0,
                      "play_count": 0, "ranked_score": 0}}
        return latest, comp, diff

    def test_four_fields_with_expected_names(self):
        latest, comp, diff = self._inputs()
        fields = w.create_player_summary_fields(
            pp_gainers=diff, rank_gainers=diff, active_players=diff,
            ranked_score_gainers=diff,
            latest_data=latest, comparison_data=comp)
        self.assertEqual(
            [f["name"] for f in fields],
            ["pp farmers", "PH rank climbers", '"play more" gamers',
             "ranked score farmers"])

    def test_zero_gains_filtered_out(self):
        latest, comp, diff = self._inputs()
        fields = w.create_player_summary_fields(
            pp_gainers=diff, rank_gainers=diff, active_players=diff,
            ranked_score_gainers=diff,
            latest_data=latest, comparison_data=comp)
        for f in fields:
            self.assertNotIn("bob", f["value"])
            self.assertIn("alice", f["value"])

    def test_lines_prefixed_with_1_current_behavior(self):
        # Intentional: Discord auto-numbers consecutive "1." lines, so the
        # code hardcodes "1." instead of enumerating. Lock it so a future
        # "fix" to enumerate is recognized as a behavior change.
        latest, comp, diff = self._inputs()
        fields = w.create_player_summary_fields(
            pp_gainers=diff, rank_gainers=diff, active_players=diff,
            ranked_score_gainers=diff,
            latest_data=latest, comparison_data=comp)
        for f in fields:
            for line in f["value"].split("\n"):
                if line.strip():
                    self.assertTrue(line.startswith("1. "),
                                    f"unexpected line: {line!r}")

    def test_limit_is_five(self):
        latest = {str(i): {"pp": 100 + i, "country_rank": i,
                           "play_count": i, "ranked_score": i}
                  for i in range(10)}
        comp = {str(i): {"pp": 100, "country_rank": 100,
                         "play_count": 0, "ranked_score": 0}
                for i in range(10)}
        diff = {str(i): {"ign": f"u{i}", "pp": i, "country_rank": 1,
                         "play_count": i, "ranked_score": i}
                for i in range(10)}
        fields = w.create_player_summary_fields(
            pp_gainers=diff, rank_gainers=diff, active_players=diff,
            ranked_score_gainers=diff,
            latest_data=latest, comparison_data=comp)
        for f in fields:
            non_empty = [ln for ln in f["value"].split("\n") if ln.strip()]
            self.assertLessEqual(len(non_empty), 5)


class TestCreateEmbedFromPlayTimestamp(unittest.TestCase):
    def _play(self, created_at):
        stats = SimpleNamespace(count_miss=0)
        beatmap = SimpleNamespace(version="Insane", difficulty_rating=5.0,
                                  url="http://example/map")
        beatmapset = SimpleNamespace(title="Song",
                                     covers=SimpleNamespace(cover="http://example/cover"))
        return SimpleNamespace(
            statistics=stats, max_combo=100, rank="S", mods="HD",
            pp=99.5, accuracy=0.99, created_at=created_at,
            beatmapset=beatmapset, beatmap=beatmap, user_id=111,
        )

    def test_minutes_not_month_regression(self):
        # Regression for the %m (month) vs %M (minutes) bug: with
        # month=01 and minutes=45 the old code emitted T10:01:30.
        user = SimpleNamespace(username="alice",
                               avatar_url="http://example/a",
                               id=111, statistics=SimpleNamespace(pp=1000.0,
                                                                  country_rank=5))
        api = SimpleNamespace(user=lambda *a, **k: user)
        play = self._play(datetime(2024, 1, 15, 10, 45, 30))
        with patch.object(w, "get_user_info", return_value=user):
            embed = w.create_embed_from_play(api, play)
        self.assertIn("T10:45:30", embed["timestamp"])
        self.assertNotIn("T10:01:30", embed["timestamp"])


class TestPpRecordListEmbed(unittest.TestCase):
    def _score(self, i):
        return SimpleNamespace(
            pp=100.0 + i,
            _user=SimpleNamespace(username=f"u{i}"),
            beatmapset=SimpleNamespace(title="Song"),
            beatmap=SimpleNamespace(version="Insane", difficulty_rating=5.0,
                                    url="http://example/map"),
            mods="HD", rank="S", accuracy=0.99,
            statistics=SimpleNamespace(count_miss=0),
            max_combo=100,
        )

    def test_numbering_starts_at_1(self):
        embed = w.create_pp_record_list_embed([self._score(0), self._score(1)])
        self.assertIn("***1.***", embed["description"])
        self.assertIn("***2.***", embed["description"])
        self.assertTrue(embed["title"].startswith("Top 5 pp records for "))


if __name__ == "__main__":
    unittest.main()
