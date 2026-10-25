"""Guards against silent data loss when score models are unexpected.

The daily workflow has no one watching it, so a model change must fail loudly
instead of producing an empty pp-records file. These tests pin:

* a missing ``ended_at`` gives a ``RuntimeError`` naming the field, not an
  ``AttributeError`` from deep inside the mapping;
* deserialization failures are not swallowed by the score-fetch retry loop
  (retrying a model shape change does not help);
* modern stable and lazer scores still pass those guards.
"""
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from ossapi import Score

import leaderboard_scrape as lb
import send_discord_webhook as sdw
from scripts import ossapi_compat as compat
from tests.ossapi_fixtures import (
    LAZER_SCORE_PAYLOAD,
    STABLE_SCORE_PAYLOAD,
    parse_model,
)


def stable_score(**overrides) -> Score:
    payload = {**STABLE_SCORE_PAYLOAD, **overrides}
    return parse_model(payload, Score, compat.OSU_API_VERSION)


def no_user_include(score: Score) -> Score:
    """Simulate osu! removing the deprecated ``user`` include."""
    score._user = None
    return score


CREDENTIALS = {"OSU_CLIENT_ID": "id", "OSU_CLIENT_SECRET": "secret"}


class TestMissingEndedAt(unittest.TestCase):
    def test_null_ended_at_is_rejected(self):
        # ossapi itself rejects a null ended_at, but a future version could
        # make it optional, so the translator guards against None as well.
        score = SimpleNamespace(ended_at=None)
        with self.assertRaises(RuntimeError) as context:
            compat.score_created_at(score)

        self.assertIn("ended_at", str(context.exception))

    def test_absent_ended_at_is_rejected(self):
        payload = dict(STABLE_SCORE_PAYLOAD)
        del payload["ended_at"]
        score = parse_model(payload, Score, compat.OSU_API_VERSION)

        with self.assertRaises(RuntimeError) as context:
            compat.score_created_at(score)
        self.assertIn("ended_at", str(context.exception))

    def test_sort_scores_by_pp_fails_loudly(self):
        score = SimpleNamespace(ended_at=None, pp=100.0)
        with self.assertRaises(RuntimeError) as context:
            lb.sort_scores_by_pp([score], top=5, max_date=4_000_000_000)
        self.assertIn("ended_at", str(context.exception))


class TestTranslationRejectsUnusableScores(unittest.TestCase):
    def test_score_without_any_id_is_rejected(self):
        payload = {
            **STABLE_SCORE_PAYLOAD, "id": None, "legacy_score_id": None,
        }
        score = parse_model(payload, Score, compat.OSU_API_VERSION)
        with self.assertRaisesRegex(RuntimeError, "id"):
            compat.score_reference_id(score)

    def test_unknown_mode_is_rejected(self):
        score = stable_score()
        with self.assertRaisesRegex(ValueError, "unsupported mode"):
            compat.score_judgement_counts(score, "not-a-mode")


class TestFetchBoundaryIsLoud(unittest.TestCase):
    def test_parse_errors_are_not_retried_away(self):
        api = MagicMock()
        api.user_scores.side_effect = TypeError(
            "unsupported operand type(s) for |: 'int' and 'dict'",
        )

        with patch.object(sdw.time, "sleep") as mock_sleep:
            with self.assertRaises(RuntimeError) as context:
                sdw.get_recent_plays_of_user(
                    api, user_id=1626093, limit=1, mode="fruits",
                )

        self.assertIn("score model", str(context.exception))
        self.assertEqual(api.user_scores.call_count, 1)
        mock_sleep.assert_not_called()

    def test_transient_errors_still_retry(self):
        api = MagicMock()
        api.user_scores.side_effect = requests.exceptions.ConnectionError(
            "flaky",
        )

        with patch.object(sdw.time, "sleep"):
            self.assertEqual(
                sdw.get_recent_plays_of_user(
                    api, user_id=1626093, limit=1, mode="fruits",
                ),
                [],
            )
        self.assertEqual(api.user_scores.call_count, 3)


class TestModernScoresAreAccepted(unittest.TestCase):
    def test_stable_score_passes_boundary(self):
        score = stable_score()
        api = SimpleNamespace(user_scores=lambda *_a, **_k: [score])
        self.assertEqual(
            sdw.get_recent_plays_of_user(
                api, user_id=1626093, limit=1, mode="fruits",
            ),
            [score],
        )

    def test_lazer_score_passes_boundary(self):
        score = parse_model(
            LAZER_SCORE_PAYLOAD, Score, compat.OSU_API_VERSION,
        )
        api = SimpleNamespace(user_scores=lambda *_a, **_k: [score])
        self.assertEqual(
            sdw.get_recent_plays_of_user(
                api, user_id=38197538, limit=1, mode="fruits",
            ),
            [score],
        )

class TestUserNamesWithoutUserInclude(unittest.TestCase):
    """osu! deprecated the `user` include on Get User Scores.

    Every consumer already has the username elsewhere (rankings file or the
    stored pp-records row), so it must not need the include.
    """

    def test_row_uses_provided_names(self):
        score = no_user_include(stable_score())
        rows = lb.format_score_data_from_list(
            [score], mode="fruits", user_names={1626093: "from-rankings"},
        )
        self.assertEqual(rows[0]["user_name"], "from-rankings")

    def test_row_still_falls_back_to_include(self):
        score = stable_score()
        rows = lb.format_score_data_from_list([score], mode="fruits")
        self.assertEqual(rows[0]["user_name"], "Maririn")

    def test_dedupe_log_does_not_need_user_include(self):
        worse = no_user_include(stable_score(pp=100.0))
        better = no_user_include(stable_score(pp=200.0))

        kept = lb.remove_duplicate_scores(
            [worse, better], user_names={1626093: "from-rankings"},
        )

        self.assertEqual(kept, [better])

    def test_pp_record_line_uses_provided_names(self):
        score = no_user_include(stable_score())
        line = sdw.format_pp_record_line(
            0, score, user_names={1626093: "from-rankings"},
        )
        self.assertIn("from-rankings", line)

    def test_pp_list_embed_uses_provided_names(self):
        score = no_user_include(stable_score())
        embed = sdw.create_pp_record_list_embed(
            [score], user_names={1626093: "from-rankings"},
        )
        self.assertIn("from-rankings", embed["description"])

    def test_get_pp_plays_uses_ranking_names(self):
        score = no_user_include(stable_score())
        processed = SimpleNamespace(
            latest_mapped_data={"1626093": {}},
            comparison_mapped_data={"1626093": {}},
            data_difference={
                "1626093": {"ign": "from-rankings", "play_count": 5},
            },
        )
        with (
            patch.object(lb, "Ossapi"),
            patch.object(
                lb, "get_comparison_and_mapped_data",
                return_value=processed,
            ),
            patch.object(
                lb, "get_recent_plays_of_user", return_value=[score],
            ),
            patch.object(
                lb, "sort_scores_by_pp",
                side_effect=lambda scores, **kwargs: scores,
            ),
            patch.dict(lb.os.environ, CREDENTIALS),
        ):
            data = lb.get_pp_plays(mode="fruits", country="PH")

        row = dict(zip(data["map"], next(iter(data["data"].values()))))
        self.assertEqual(row["user_name"], "from-rankings")

    def test_webhook_uses_names_from_stored_rows(self):
        score = no_user_include(stable_score())
        raw_scores = {
            "map": ["user_id", "user_name", "score_type"],
            "data": {"225335112": [1626093, "from-rankings", "old"]},
        }
        sent_embeds = []

        def capture_webhook(**kwargs):
            sent_embeds.append(kwargs["embeds"][0])

        with (
            patch.object(
                sdw, "get_data_at_date", return_value=raw_scores,
            ),
            patch.object(sdw, "fetch_top_scores", return_value=[score]),
            patch.object(sdw, "send_webhook", side_effect=capture_webhook),
            patch.object(
                sdw, "create_embed_from_play",
                return_value={"title": "top play"},
            ),
        ):
            sdw.send_play_pp_ranking_webhook(
                api=None,
                latest_timestamp=datetime(2026, 10, 25),
                mode="fruits",
                country="PH",
                test=True,
            )

        self.assertIn("from-rankings", sent_embeds[0]["description"])


if __name__ == "__main__":
    unittest.main()
