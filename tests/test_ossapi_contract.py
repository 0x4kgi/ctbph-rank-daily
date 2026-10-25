"""Contract tests for ossapi 5.3.6 with modern (x-api-version 20241024) scores.

Two jobs:
1. Pin the client configuration: the version we request, the header osu!
   actually reads, and every ``Ossapi(...)`` construction site.
2. Translate recorded modern payloads through ossapi's real model machinery and
   assert the legacy JSON rows/embeds this project has always produced, so a
   model change shows up here instead of in the daily workflow.

Guards for broken/incomplete responses live in ``test_ossapi_robustness.py``.
"""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ossapi import GameMode, Score, models
from ossapi.ossapiv2 import Oauth2SessionOssapi

import leaderboard_scrape as lb
import send_discord_webhook as sdw
from scripts import ossapi_compat as compat
from tests.ossapi_fixtures import (
    LAZER_SCORE_PAYLOAD,
    RANKING_PAYLOAD,
    STABLE_SCORE_PAYLOAD,
    parse_model,
)

EXPECTED_STABLE_ROW = {
    "score_id": 225335112,
    "score_type": "old",
    "score_mods": "HRHD",
    "score_pp": 544.464,
    "score_grade": "SH",
    "user_id": 1626093,
    "user_name": "Maririn",
    "beatmapset_title": "Ignite (Cut Ver.)",
    "beatmap_version": "Deluge",
    "beatmap_id": 5882157,
    "beatmapset_id": 2617876,
    "beatmap_difficulty": 6.04865,
    "full_combo": True,
    "max_combo": 751,
    "count_300": 745,
    "count_100": 6,
    "count_50": 59,
    "count_droplet_miss": 2,
    "count_miss": 0,
    "accuracy": 0.997537,
}

EXPECTED_LAZER_ROW = {
    "score_id": 7764291310,
    "score_type": "new",
    "score_mods": "NM",
    "score_pp": 8.0315,
    "score_grade": "A",
    "user_id": 38197538,
    "user_name": "F1orence",
    "beatmapset_title": "Melissa (TV size ver.)",
    "beatmap_version": "Tt's Hard",
    "beatmap_id": 916931,
    "beatmapset_id": 423500,
    "beatmap_difficulty": 1.94943,
    "full_combo": False,
    "max_combo": 84,
    "count_300": 462,
    "count_100": 0,
    "count_50": 310,
    "count_droplet_miss": 18,
    "count_miss": 23,
    "accuracy": 0.94957,
}

EXPECTED_RANKING_ROW = {
    "country_rank": 2,
    "global_rank": 26,
    "id": 829284,
    "ign": "Bunnrei",
    "pp": 21823,
    "acc": 99.9052,
    "play_count": 156721,
    "rank_x": 865,
    "rank_s": 1735,
    "rank_a": 127,
    "play_time": 6504127,
    "total_score": 814886486317,
    "ranked_score": 85052826495,
    "total_hits": 60163628,
}

CREDENTIALS = {"OSU_CLIENT_ID": "id", "OSU_CLIENT_SECRET": "secret"}


def stable_score(**overrides) -> Score:
    payload = {**STABLE_SCORE_PAYLOAD, **overrides}
    return parse_model(payload, Score, compat.OSU_API_VERSION)


def lazer_score(**overrides) -> Score:
    payload = {**LAZER_SCORE_PAYLOAD, **overrides}
    return parse_model(payload, Score, compat.OSU_API_VERSION)


class TestApiVersionPin(unittest.TestCase):
    def test_pin_is_a_modern_version(self):
        self.assertEqual(compat.OSU_API_VERSION, 20241024)
        self.assertEqual(lb.OSU_API_VERSION, compat.OSU_API_VERSION)
        self.assertEqual(sdw.OSU_API_VERSION, compat.OSU_API_VERSION)

    def test_pinned_header_is_sent(self):
        # This is the value osu! switches score models on.
        session = Oauth2SessionOssapi(
            client_id="test-client", api_version=compat.OSU_API_VERSION,
        )
        self.assertEqual(session.headers["x-api-version"], "20241024")

    def test_get_page_rankings_pins_version(self):
        with patch.object(lb, "Ossapi") as mock_cls, \
                patch.dict(lb.os.environ, CREDENTIALS):
            mock_cls.return_value.ranking.return_value = SimpleNamespace(
                ranking=[],
            )
            self.assertEqual(
                lb.get_page_rankings(page=1, mode="fruits", country="PH"),
                [],
            )
        mock_cls.assert_called_once_with(
            "id", "secret", api_version=compat.OSU_API_VERSION,
        )

    def test_get_pp_plays_pins_version(self):
        no_data = SimpleNamespace(
            latest_mapped_data=None,
            comparison_mapped_data=None,
            data_difference=None,
        )
        with patch.object(lb, "Ossapi") as mock_cls, \
                patch.object(
                    lb, "get_comparison_and_mapped_data",
                    return_value=no_data,
                ), \
                patch.dict(lb.os.environ, CREDENTIALS):
            self.assertIsNone(lb.get_pp_plays(mode="fruits", country="PH"))
        mock_cls.assert_called_once_with(
            "id", "secret", api_version=compat.OSU_API_VERSION,
        )

    def test_webhook_entrypoint_pins_version(self):
        no_data = SimpleNamespace(
            latest_mapped_data=None,
            comparison_mapped_data=None,
            data_difference=None,
        )
        with patch.object(sdw, "Ossapi") as mock_cls, \
                patch.object(
                    sdw, "get_comparison_and_mapped_data",
                    return_value=no_data,
                ), \
                patch.dict(sdw.os.environ, CREDENTIALS):
            sdw.main()
        mock_cls.assert_called_once_with(
            "id", "secret", api_version=compat.OSU_API_VERSION,
        )


class TestScoreFieldTranslation(unittest.TestCase):
    def test_created_at_comes_from_ended_at(self):
        score = stable_score()
        self.assertEqual(compat.score_created_at(score), score.ended_at)
        self.assertEqual(
            compat.score_created_at(score).isoformat(),
            "2026-10-08T16:45:15+00:00",
        )

    def test_stable_score_uses_legacy_reference_id(self):
        score = stable_score()
        self.assertTrue(compat.has_legacy_score_id(score))
        self.assertEqual(compat.score_reference_id(score), 225335112)

    def test_lazer_score_uses_modern_reference_id(self):
        score = lazer_score()
        self.assertFalse(compat.has_legacy_score_id(score))
        self.assertEqual(compat.score_reference_id(score), 7764291310)

    def test_mods_drop_cl_on_stable_scores(self):
        # Recorded stable score: mods are [HR, HD, CL] in API order.
        self.assertEqual(compat.score_mods_text(stable_score()), "HRHD")

    def test_mods_keep_cl_on_lazer_scores(self):
        score = lazer_score(
            mods=[{"acronym": "HD"}, {"acronym": "CL"}],
        )
        self.assertEqual(compat.score_mods_text(score), "HDCL")

    def test_no_mods_is_nm(self):
        self.assertEqual(compat.score_mods_text(lazer_score()), "NM")

    def test_stable_scores_use_legacy_perfect(self):
        score = stable_score(
            legacy_perfect=False, is_perfect_combo=True,
        )
        self.assertFalse(compat.score_full_combo(score))

    def test_lazer_scores_use_is_perfect_combo(self):
        score = lazer_score(
            legacy_perfect=False, is_perfect_combo=True,
        )
        self.assertTrue(compat.score_full_combo(score))

    def test_miss_count_defaults_to_zero(self):
        self.assertEqual(compat.score_miss_count(stable_score()), 0)
        self.assertEqual(compat.score_miss_count(lazer_score()), 23)

    def test_catch_judgements_match_osu_web_mapping(self):
        self.assertEqual(
            compat.score_judgement_counts(stable_score(), "fruits"),
            {
                "count_300": 745,
                "count_100": 6,
                "count_50": 59,
                "count_katu": 2,
                "count_miss": 0,
            },
        )

    def test_other_rulesets_use_their_own_mapping(self):
        statistics = SimpleNamespace(
            great=200, ok=10, meh=2, good=4, miss=1,
        )
        score = SimpleNamespace(statistics=statistics)
        self.assertEqual(
            compat.score_judgement_counts(score, "osu"),
            {"count_300": 200, "count_100": 10, "count_50": 2,
             "count_miss": 1},
        )
        self.assertEqual(
            compat.score_judgement_counts(score, GameMode.MANIA),
            {"count_300": 200, "count_100": 10, "count_50": 2,
             "count_katu": 4, "count_miss": 1},
        )


class TestScoreRowTranslation(unittest.TestCase):
    def test_stable_score_row(self):
        self.assertEqual(
            lb.format_score_data_from_list([stable_score()], mode="fruits"),
            [EXPECTED_STABLE_ROW],
        )

    def test_lazer_score_row(self):
        self.assertEqual(
            lb.format_score_data_from_list([lazer_score()], mode="fruits"),
            [EXPECTED_LAZER_ROW],
        )

    def test_sort_scores_by_pp_uses_ended_at(self):
        score = stable_score()
        self.assertEqual(
            lb.sort_scores_by_pp(
                [score],
                top=5,
                max_date=score.ended_at.timestamp() + 1,
            ),
            [score],
        )

    def test_create_embed_from_play(self):
        score = stable_score()
        fake_user = SimpleNamespace(
            username="Maririn",
            avatar_url="https://a.ppy.sh/1626093",
            id=1626093,
            statistics=SimpleNamespace(pp=17760.0, country_rank=4),
        )
        with patch.object(sdw, "get_user_info", return_value=fake_user):
            embed = sdw.create_embed_from_play(None, score)

        self.assertEqual(embed["timestamp"], "2026-10-08T16:45:15.000000Z")
        self.assertEqual(
            embed["title"], "Ignite (Cut Ver.) [Deluge] [6.05★]",
        )
        self.assertEqual(embed["fields"][1]["value"], "99.75%")
        self.assertEqual(embed["fields"][2]["value"], "HRHD")
        self.assertEqual(embed["url"], "https://osu.ppy.sh/beatmaps/5882157")
        self.assertEqual(
            embed["image"]["url"],
            "https://assets.ppy.sh/beatmaps/2617876/covers/cover.jpg",
        )
        self.assertEqual(
            embed["author"]["name"], "Maririn • 17,760pp • PH4",
        )
        self.assertIn("FC", embed["description"])

    def test_pp_record_line_uses_translated_mods(self):
        line = sdw.format_pp_record_line(0, stable_score())
        self.assertIn("+HRHD", line)
        self.assertIn("FC", line)


class TestFetchTopScoresRouting(unittest.TestCase):
    def test_stable_row_fetches_by_legacy_id(self):
        score = stable_score()
        row = lb.format_score_data_from_list([score], mode="fruits")[0]
        api = MagicMock()
        api.score_mode.return_value = score

        result = sdw.fetch_top_scores(
            api, {row["score_id"]: row}, mode="fruits", top=1,
        )

        self.assertEqual(result, [score])
        api.score_mode.assert_called_once_with(
            GameMode.CATCH, 225335112,
        )
        api.score.assert_not_called()

    def test_lazer_row_fetches_by_modern_id(self):
        score = lazer_score()
        row = lb.format_score_data_from_list([score], mode="fruits")[0]
        api = MagicMock()
        api.score.return_value = score

        result = sdw.fetch_top_scores(
            api, {row["score_id"]: row}, mode="fruits", top=1,
        )

        self.assertEqual(result, [score])
        api.score.assert_called_once_with(7764291310)
        api.score_mode.assert_not_called()


class TestRankingsContract(unittest.TestCase):
    def test_format_data_from_rows(self):
        rankings = parse_model(
            RANKING_PAYLOAD, models.Rankings, compat.OSU_API_VERSION,
        )
        self.assertEqual(
            lb.format_data_from_rows(rankings),
            [EXPECTED_RANKING_ROW],
        )

    def test_rankings_are_version_independent(self):
        # Only score models sit behind the api_version switch.
        pinned = parse_model(
            RANKING_PAYLOAD, models.Rankings, compat.OSU_API_VERSION,
        )
        legacy = parse_model(RANKING_PAYLOAD, models.Rankings, 0)
        self.assertEqual(
            lb.format_data_from_rows(pinned),
            lb.format_data_from_rows(legacy),
        )


if __name__ == "__main__":
    unittest.main()
