"""Deprecation drills for the legacy score format.

Context: with ``api_version=0`` ossapi sends ``x-api-version: 0`` and osu!
returns legacy score models. If osu! ever stops honoring that header, the API
returns modern scores and today:

* scores with mods fail inside ossapi (``TypeError`` from ``Mod`` parsing) and
  ``get_recent_plays_of_user`` swallows it after three retries, leaving an
  empty pp-records file and a green workflow;
* scores without mods parse with every legacy field missing, so they either
  crash deep inside the mapping or get dropped silently when ``pp`` is null.

These tests pin the behavior we want instead: a loud ``RuntimeError`` that
names ``legacy score format`` and ``api_version``, with no pointless retries.
They are expected to fail until the guard is implemented.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ossapi import Score

import leaderboard_scrape as lb
import send_discord_webhook as sdw
from tests.ossapi_fixtures import (
    LEGACY_SCORE_PAYLOAD,
    MODERN_SCORE_PAYLOAD,
    parse_model,
)

LEGACY_FAILURE = "legacy score format"
API_VERSION_HINT = "api_version"


def modern_score() -> Score:
    """Score as the API returns it at api_version >= 20220705."""
    return parse_model(MODERN_SCORE_PAYLOAD, Score, 20241024)


def modern_payload_parsed_as_legacy(*_args, **_kwargs):
    """Reproduce what ossapi raises when osu! ignores api_version=0.

    Modern mods are dicts, so ``Mod`` construction fails with a TypeError
    before ``user_scores`` can return anything.
    """
    parse_model(MODERN_SCORE_PAYLOAD, Score, 0)


class TestModernScoresAreRejected(unittest.TestCase):
    def test_format_score_data_from_list(self):
        with self.assertRaises(RuntimeError) as context:
            lb.format_score_data_from_list([modern_score()])

        message = str(context.exception)
        self.assertIn(LEGACY_FAILURE, message)
        self.assertIn(API_VERSION_HINT, message)

    def test_sort_scores_by_pp(self):
        score = modern_score()
        with self.assertRaises(RuntimeError) as context:
            lb.sort_scores_by_pp(
                [score],
                max_date=score.ended_at.timestamp() + 1,
            )
        self.assertIn(LEGACY_FAILURE, str(context.exception))

    def test_create_embed_from_play(self):
        fake_user = SimpleNamespace(
            username="Maririn",
            avatar_url="https://a.ppy.sh/1626093",
            id=1626093,
            statistics=SimpleNamespace(pp=17760.0, country_rank=4),
        )
        with patch.object(sdw, "get_user_info", return_value=fake_user):
            with self.assertRaises(RuntimeError) as context:
                sdw.create_embed_from_play(None, modern_score())
        self.assertIn(LEGACY_FAILURE, str(context.exception))

    def test_fetch_top_scores(self):
        score = modern_score()
        api = SimpleNamespace(score_mode=lambda *_a, **_k: score)
        mapped_scores = {225335112: {"score_type": "old"}}

        with self.assertRaises(RuntimeError) as context:
            sdw.fetch_top_scores(api, mapped_scores, mode="fruits", top=1)
        self.assertIn(LEGACY_FAILURE, str(context.exception))


class TestFetchBoundaryIsLoud(unittest.TestCase):
    def test_unparseable_scores_are_not_swallowed(self):
        api = MagicMock()
        api.user_scores.side_effect = modern_payload_parsed_as_legacy

        with patch.object(sdw.time, "sleep") as mock_sleep:
            with self.assertRaises(RuntimeError) as context:
                sdw.get_recent_plays_of_user(
                    api, user_id=1626093, limit=1, mode="fruits",
                )

        message = str(context.exception)
        self.assertIn(LEGACY_FAILURE, message)
        self.assertIn(API_VERSION_HINT, message)
        self.assertEqual(api.user_scores.call_count, 1)
        mock_sleep.assert_not_called()

    def test_partially_parsed_modern_scores_are_rejected(self):
        # A modern payload with no mods parses without raising, but every
        # legacy field is missing. The boundary must reject it instead of
        # letting it fail later or be dropped as "no pp".
        score = parse_model(
            {**MODERN_SCORE_PAYLOAD, "mods": []}, Score, 0,
        )
        self.assertFalse(hasattr(score, "created_at"))
        api = SimpleNamespace(user_scores=lambda *_a, **_k: [score])

        with self.assertRaises(RuntimeError) as context:
            sdw.get_recent_plays_of_user(
                api, user_id=1626093, limit=1, mode="fruits",
            )
        self.assertIn(LEGACY_FAILURE, str(context.exception))


class TestLegacyScoresStillPass(unittest.TestCase):
    """Guards against a shape check that rejects the happy path."""

    def test_fetch_boundary_accepts_legacy_scores(self):
        score = parse_model(LEGACY_SCORE_PAYLOAD, Score, 0)
        api = SimpleNamespace(user_scores=lambda *_a, **_k: [score])

        self.assertEqual(
            sdw.get_recent_plays_of_user(
                api, user_id=1626093, limit=1, mode="fruits",
            ),
            [score],
        )

    def test_fetch_top_scores_accepts_legacy_scores(self):
        score = parse_model(LEGACY_SCORE_PAYLOAD, Score, 0)
        api = SimpleNamespace(score_mode=lambda *_a, **_k: score)
        mapped_scores = {225335112: {"score_type": "old"}}

        self.assertEqual(
            sdw.fetch_top_scores(api, mapped_scores, mode="fruits", top=1),
            [score],
        )


if __name__ == "__main__":
    unittest.main()
