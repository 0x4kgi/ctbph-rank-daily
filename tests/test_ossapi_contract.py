"""Contract tests for our ossapi 5.3.6 integration.

Two jobs:
1. Pin the client configuration that keeps osu! returning legacy score models
   (``api_version=0``), including the ``x-api-version`` header itself.
2. Run recorded API payloads through ossapi's real model machinery, so a
   model shape change shows up here instead of in the daily workflow.

The deprecation drills (what must happen if osu! stops honoring the pin) live
in ``test_ossapi_deprecation.py``.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ossapi import Score, models
from ossapi.ossapiv2 import Oauth2SessionOssapi

import leaderboard_scrape as lb
import scripts.sanity_check as sc
import send_discord_webhook as sdw
from tests.ossapi_fixtures import (
    LEGACY_SCORE_PAYLOAD,
    RANKING_PAYLOAD,
    parse_model,
)

EXPECTED_LEGACY_ROW = {
    "score_id": 225335112,
    "score_type": "old",
    "score_mods": "HDHR",
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
    "accuracy": 0.9975369458128078,
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


class TestApiVersionPin(unittest.TestCase):
    def test_pin_constants_are_legacy(self):
        self.assertEqual(lb.OSU_API_VERSION, 0)
        self.assertEqual(sdw.OSU_API_VERSION, 0)
        self.assertEqual(sc.OSU_API_VERSION, 0)

    def test_legacy_header_is_sent(self):
        # This header is the actual switch osu! reads. "0" means "before the
        # 2022-07-05 score format", i.e. the legacy models this project uses.
        session = Oauth2SessionOssapi(client_id="test-client", api_version=0)
        self.assertEqual(session.headers["x-api-version"], "0")

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
        mock_cls.assert_called_once_with("id", "secret", api_version=0)

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
        mock_cls.assert_called_once_with("id", "secret", api_version=0)

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
        mock_cls.assert_called_once_with("id", "secret", api_version=0)

    def test_sanity_check_pins_version(self):
        with patch.object(sc, "Ossapi") as mock_cls, \
                patch.object(sc, "load_dotenv"), \
                patch.object(
                    sc.requests, "post",
                    return_value=SimpleNamespace(status_code=204),
                ), \
                patch.dict(sc.os.environ, CREDENTIALS):
            sc.main()
        mock_cls.assert_called_once_with("id", "secret", api_version=0)


class TestLegacyScoreContract(unittest.TestCase):
    def test_model_exposes_legacy_fields(self):
        score = parse_model(LEGACY_SCORE_PAYLOAD, Score, 0)

        self.assertEqual(score.created_at.isoformat(),
                         "2026-10-08T16:45:15+00:00")
        self.assertTrue(score.perfect)
        self.assertEqual(str(score.mods), "HDHR")
        self.assertEqual(score.statistics.count_300, 745)
        self.assertEqual(score.statistics.count_100, 6)
        self.assertEqual(score.statistics.count_50, 59)
        self.assertEqual(score.statistics.count_katu, 2)
        self.assertEqual(score.statistics.count_miss, 0)

    def test_format_score_data_from_list(self):
        score = parse_model(LEGACY_SCORE_PAYLOAD, Score, 0)
        self.assertEqual(
            lb.format_score_data_from_list([score]),
            [EXPECTED_LEGACY_ROW],
        )

    def test_sort_scores_by_pp_keeps_legacy_score(self):
        score = parse_model(LEGACY_SCORE_PAYLOAD, Score, 0)
        sorted_scores = lb.sort_scores_by_pp(
            [score],
            top=5,
            max_date=score.created_at.timestamp() + 1,
        )
        self.assertEqual(sorted_scores, [score])

    def test_create_embed_from_play(self):
        score = parse_model(LEGACY_SCORE_PAYLOAD, Score, 0)
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
        self.assertEqual(embed["fields"][2]["value"], "HDHR")
        self.assertEqual(embed["url"], "https://osu.ppy.sh/beatmaps/5882157")
        self.assertEqual(
            embed["image"]["url"],
            "https://assets.ppy.sh/beatmaps/2617876/covers/cover.jpg",
        )
        self.assertEqual(
            embed["author"]["name"], "Maririn • 17,760pp • PH4",
        )
        self.assertIn("FC", embed["description"])

    def test_double_digit_score_id_is_new_format(self):
        # Only the id differs: format_score_data_from_list reads nothing else
        # for the old/new split.
        score = parse_model(
            {**LEGACY_SCORE_PAYLOAD, "id": 7649769528}, Score, 0,
        )
        row = lb.format_score_data_from_list([score])[0]
        self.assertEqual(row["score_id"], 7649769528)
        self.assertEqual(row["score_type"], "new")


class TestRankingsContract(unittest.TestCase):
    def test_format_data_from_rows(self):
        rankings = parse_model(RANKING_PAYLOAD, models.Rankings, 0)
        self.assertEqual(
            lb.format_data_from_rows(rankings),
            [EXPECTED_RANKING_ROW],
        )

    def test_rankings_are_version_independent(self):
        # Only score models are behind the api_version switch; rankings must
        # keep parsing whichever version we pin.
        legacy = parse_model(RANKING_PAYLOAD, models.Rankings, 0)
        modern = parse_model(RANKING_PAYLOAD, models.Rankings, 20241024)
        self.assertEqual(
            lb.format_data_from_rows(legacy),
            lb.format_data_from_rows(modern),
        )


if __name__ == "__main__":
    unittest.main()
