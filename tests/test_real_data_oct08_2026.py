"""Golden-data test: daily update for Oct 08, 2026.

Locks the Discord-visible numbers for one known-good day so future
refactors of the diff/format/webhook code can't silently change them.

Sources (committed to the repo, treated as immutable fixtures):
- docs/data/2026/10/07/PH-fruits.json
- docs/data/2026/10/08/PH-fruits.json
- docs/data/2026/10/08/PH-fruits-pp-records.json

Cross-checked against the live Discord embeds from that day.

Headline numbers for the day: 42 played, 13 pp gainers, 8 PH climbers,
+407pp, +96 ranks, +1,135 plays, +1.34B ranked score.
"""
import json
import os
import unittest
from datetime import datetime

from scripts.general_utils import simplify_number
from scripts.json_player_data import (
    compare_player_data,
    get_comparison_and_mapped_data,
    get_sorted_dict_on_stat,
    map_player_data,
)
from send_discord_webhook import (
    create_player_summary_fields,
    description_maker,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAY07 = os.path.join(ROOT, "docs/data/2026/10/07/PH-fruits.json")
DAY08 = os.path.join(ROOT, "docs/data/2026/10/08/PH-fruits.json")
PP08 = os.path.join(ROOT, "docs/data/2026/10/08/PH-fruits-pp-records.json")


def _load(path):
    with open(path) as f:
        return json.load(f)


class TestFixtureSanity(unittest.TestCase):
    def test_ranking_files_cover_top_1000(self):
        for path in (DAY07, DAY08):
            with self.subTest(path=path):
                raw = _load(path)
                self.assertEqual(raw["mode"], "fruits")
                self.assertEqual(raw["country"], "PH")
                self.assertEqual(raw["file_version"], 1.01)
                self.assertEqual(len(raw["data"]), 1000)
                self.assertIn("pp", raw["map"])
                self.assertIn("play_count", raw["map"])

    def test_pp_records_file_has_100_entries(self):
        raw = _load(PP08)
        self.assertEqual(raw["type"], "pp-records")
        self.assertEqual(raw["file_version"], 1.011)
        self.assertEqual(len(raw["data"]), 100)


class TestOct08Headlines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        res = get_comparison_and_mapped_data(
            base_date=datetime(2026, 10, 8),
            compare_date_offset=1,
            country="PH",
            mode="fruits",
            test=False,
        )
        cls.latest = res.latest_mapped_data
        cls.comp = res.comparison_mapped_data
        cls.diff = compare_player_data(cls.latest, cls.comp)

    def _above(self, stat):
        return sum(1 for v in self.diff.values() if v.get(stat, 0) > 0)

    def _total(self, stat):
        return sum(v[stat] for v in self.diff.values() if v.get(stat, 0) > 0)

    def test_headline_counts(self):
        self.assertEqual(self._above("play_count"), 42)
        self.assertEqual(self._above("pp"), 13)
        self.assertEqual(self._above("country_rank"), 8)

    def test_headline_totals(self):
        self.assertEqual(self._total("pp"), 407)
        self.assertEqual(self._total("country_rank"), 96)
        self.assertEqual(self._total("play_count"), 1135)
        self.assertEqual(self._total("ranked_score"), 1338066619)
        self.assertEqual(
            simplify_number(self._total("ranked_score")), "1.34B")

    def test_description_carries_headlines(self):
        desc = description_maker(
            get_sorted_dict_on_stat(self.diff, "play_count", True),
            get_sorted_dict_on_stat(self.diff, "pp", True),
            get_sorted_dict_on_stat(self.diff, "country_rank", True),
            get_sorted_dict_on_stat(self.diff, "ranked_score", True),
        )
        for snippet in ("**42** players who played",
                        "**13** players who saw pp gains",
                        "**8** players who climbed the PH ranks",
                        "**407pp**", "**96 ranks**",
                        "**1,135 play count**", "**1.34B ranked score**"):
            self.assertIn(snippet, desc)


class TestOct08SpotChecks(unittest.TestCase):
    # uid -> (old, new) per stat, plus expected diff
    PLAYERS = {
        # pp farmers
        "11908038": {"ign": "vgames9",
                     "pp": (670, 821, 151)},
        "17166294": {"ign": "Alloice",
                     "pp": (5047, 5079, 32)},
        # PH rank climbers
        "34066862": {"ign": "twtthomasgoatz",
                     "country_rank": (416, 406, 10)},
        "10652837": {"ign": "Rammu",
                     "country_rank": (226, 223, 3)},
        # play count grinders
        "1626093": {"ign": "Maririn",
                    "play_count": (226077, 226241, 164)},
        "17745759": {"ign": "-Isla-",
                     "play_count": (44138, 44252, 114)},
        # ranked score farmers
        "10373568": {"ign": "Lawrence Angelo",
                     "ranked_score": (11155068584, 11198273680, 43205096)},
        "23694332": {"ign": "RamSenpaiTZY",
                     "ranked_score": (3773278565, 3831470846, 58192281)},
    }

    @classmethod
    def setUpClass(cls):
        cls.latest = map_player_data(_load(DAY08))
        cls.comp = map_player_data(_load(DAY07))
        cls.diff = compare_player_data(cls.latest, cls.comp)

    def test_spot_values(self):
        for uid, specs in self.PLAYERS.items():
            with self.subTest(ign=specs["ign"]):
                self.assertEqual(self.latest[uid]["ign"], specs["ign"])
                for stat, vals in specs.items():
                    if stat == "ign":
                        continue
                    old, new, gained = vals
                    self.assertEqual(self.comp[uid][stat], old)
                    self.assertEqual(self.latest[uid][stat], new)
                    self.assertEqual(self.diff[uid][stat], gained)

    def test_ranked_score_simplifications(self):
        self.assertEqual(simplify_number(11155068584), "11.16B")
        self.assertEqual(simplify_number(11198273680), "11.20B")
        self.assertEqual(simplify_number(43205096), "43.21M")
        self.assertEqual(simplify_number(3773278565), "3.77B")
        self.assertEqual(simplify_number(3831470846), "3.83B")
        self.assertEqual(simplify_number(58192281), "58.19M")

    def test_embed_lines_for_known_players(self):
        fields = create_player_summary_fields(
            pp_gainers=get_sorted_dict_on_stat(self.diff, "pp", True),
            rank_gainers=get_sorted_dict_on_stat(self.diff, "country_rank", True),
            active_players=get_sorted_dict_on_stat(self.diff, "play_count", True),
            ranked_score_gainers=get_sorted_dict_on_stat(
                self.diff, "ranked_score", True),
            latest_data=self.latest,
            comparison_data=self.comp,
        )
        by_name = {f["name"]: f["value"] for f in fields}
        # pp farmers: vgames9 is #1 that day
        first_pp_line = by_name["pp farmers"].split("\n")[0]
        self.assertIn("[**vgames9**](https://osu.ppy.sh/users/11908038/fruits)",
                      first_pp_line)
        self.assertIn("670pp", first_pp_line)
        self.assertIn("**821**pp", first_pp_line)
        self.assertIn("+**151**pp", first_pp_line)
        # PH rank climbers
        self.assertIn("PH416", by_name["PH rank climbers"])
        self.assertIn("PH**406**", by_name["PH rank climbers"])
        self.assertIn("PH226", by_name["PH rank climbers"])
        self.assertIn("PH**223**", by_name["PH rank climbers"])
        # play count grinders
        self.assertIn("226,077", by_name['"play more" gamers'])
        self.assertIn("226,241", by_name['"play more" gamers'])
        self.assertIn("44,138", by_name['"play more" gamers'])
        self.assertIn("44,252", by_name['"play more" gamers'])
        # ranked score farmers (simplified)
        self.assertIn("11.16B", by_name["ranked score farmers"])
        self.assertIn("11.20B", by_name["ranked score farmers"])
        self.assertIn("43.21M", by_name["ranked score farmers"])
        self.assertIn("3.77B", by_name["ranked score farmers"])
        self.assertIn("3.83B", by_name["ranked score farmers"])
        self.assertIn("58.19M", by_name["ranked score farmers"])


class TestOct08TopPlays(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scores = map_player_data(_load(PP08))

    def _top(self):
        return sorted(self.scores.items(),
                      key=lambda kv: kv[1]["score_pp"] or 0,
                      reverse=True)[0]

    def test_best_play_is_maririn_ignite_deluge(self):
        sid, best = self._top()
        self.assertEqual(best["user_name"], "Maririn")
        self.assertEqual(best["beatmapset_title"], "Ignite (Cut Ver.)")
        self.assertEqual(best["beatmap_version"], "Deluge")
        self.assertAlmostEqual(best["beatmap_difficulty"], 6.05, places=2)
        self.assertAlmostEqual(best["accuracy"] * 100, 99.75, places=2)
        self.assertEqual(best["count_miss"], 0)
        self.assertEqual(best["score_mods"], "HDHR")
        self.assertAlmostEqual(best["score_pp"], 544.46, places=2)
        self.assertTrue(best["full_combo"])

    def test_expected_players_present(self):
        names = {s["user_name"] for s in self.scores.values()}
        for player in ("Sirelia", "Laqure", "Happy_566", "Maririn"):
            self.assertIn(player, names)

    def test_expected_maps_present(self):
        titles = {s["beatmapset_title"] for s in self.scores.values()}
        for title in ("#sawg (Wan Bushi Remix)",
                      "Tetoris x Override",
                      "Ai Dua Em Ve (Cukak Remix) "
                      "(Agnes Tachyon Low Cortisol Edit) (Cut Ver.)",
                      "Ignite (Cut Ver.)"):
            self.assertIn(title, titles)


if __name__ == "__main__":
    unittest.main()
