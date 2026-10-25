"""Recorded osu! API payloads and a real-model loader for tests.

Payloads were captured from the live v2 API on 2026-10-25 and trimmed to the
fields this project reads. ``parse_model`` runs the same deserialization path
as ``Ossapi._request`` (without OAuth or network), so these tests fail if
ossapi changes a model shape. The SimpleNamespace fakes in the other test
modules cannot catch that.
"""
import copy
import logging

from ossapi import Ossapi

# /scores/fruits/225335112 with x-api-version: 0 (legacy score shape).
LEGACY_SCORE_PAYLOAD = {
    "id": 225335112,
    "best_id": 225335112,
    "user_id": 1626093,
    "accuracy": 0.9975369458128078,
    "mods": ["HD", "HR"],
    "score": 26000000,
    "max_combo": 751,
    "perfect": True,
    "statistics": {
        "count_100": 6,
        "count_300": 745,
        "count_50": 59,
        "count_geki": None,
        "count_katu": 2,
        "count_miss": 0,
    },
    "pp": 544.464,
    "rank": "SH",
    "created_at": "2026-10-08T16:45:15Z",
    "mode": "fruits",
    "mode_int": 2,
    "replay": True,
    "passed": True,
    "current_user_attributes": {},
    "beatmap": {
        "id": 5882157,
        "version": "Deluge",
        "difficulty_rating": 6.04865,
        "url": "https://osu.ppy.sh/beatmaps/5882157",
    },
    "beatmapset": {
        "id": 2617876,
        "title": "Ignite (Cut Ver.)",
        "covers": {
            "cover": "https://assets.ppy.sh/beatmaps/2617876/covers/cover.jpg",
        },
    },
    "rank_country": None,
    "rank_global": None,
    "weight": None,
    "user": {"id": 1626093, "username": "Maririn"},
    "match": None,
    "type": "score_best_fruits",
}

# The same score with x-api-version: 20241024 (modern score shape).
# Note: modern mods are dicts, and the CL (Classic) mod is added by lazer.
MODERN_SCORE_PAYLOAD = {
    "id": 7653394134,
    "best_id": 7653394134,
    "legacy_score_id": 225335112,
    "user_id": 1626093,
    "accuracy": 0.997537,
    "max_combo": 751,
    "pp": 544.464,
    "rank": "SH",
    "mods": [{"acronym": "HR"}, {"acronym": "HD"}, {"acronym": "CL"}],
    "legacy_perfect": True,
    "is_perfect_combo": True,
    "ended_at": "2026-10-08T16:45:15Z",
    "started_at": None,
    "statistics": {
        "great": 745,
        "large_tick_hit": 6,
        "small_tick_hit": 59,
        "small_tick_miss": 2,
    },
    "passed": True,
    "current_user_attributes": {},
    "classic_total_score": 26000000,
    "processed": True,
    "replay": True,
    "maximum_statistics": {"great": 745},
    "ruleset_id": 2,
    "ranked": True,
    "preserve": True,
    "beatmap_id": 5882157,
    "build_id": None,
    "has_replay": True,
    "total_score": 26000000,
    "total_score_without_mods": 20000000,
    "legacy_total_score": 26000000,
    "beatmap": {
        "id": 5882157,
        "version": "Deluge",
        "difficulty_rating": 6.04865,
        "url": "https://osu.ppy.sh/beatmaps/5882157",
    },
    "beatmapset": {
        "id": 2617876,
        "title": "Ignite (Cut Ver.)",
        "covers": {
            "cover": "https://assets.ppy.sh/beatmaps/2617876/covers/cover.jpg",
        },
    },
    "rank_country": None,
    "rank_global": None,
    "weight": None,
    "user": {"id": 1626093, "username": "Maririn"},
    "match": None,
    "type": "solo_score",
}

# /rankings/fruits/performance?country=PH, trimmed to one player.
RANKING_PAYLOAD = {
    "cursor": {"page": 2},
    "cursor_string": "abc123",
    "ranking": [{
        "country_rank": 2,
        "global_rank": 26,
        "hit_accuracy": 99.9052,
        "play_count": 156721,
        "play_time": 6504127,
        "total_score": 814886486317,
        "ranked_score": 85052826495,
        "total_hits": 60163628,
        "pp": 21823.3,
        "grade_counts": {
            "ss": 723,
            "ssh": 142,
            "s": 1408,
            "sh": 327,
            "a": 127,
        },
        "user": {"id": 829284, "username": "Bunnrei"},
    }],
    "total": 6977,
}


def fake_ossapi(api_version: int) -> Ossapi:
    """Ossapi instance with OAuth and network bypassed, for model parsing."""
    api = Ossapi.__new__(Ossapi)
    api.api_version = api_version
    api.strict = False
    api.log = logging.getLogger(__name__)
    api._type_hints_cache = {}
    return api


def parse_model(payload: dict, model, api_version: int):
    """Deserialize a payload exactly like ``Ossapi._request`` would.

    A deep copy keeps the module-level payloads reusable: ossapi mutates the
    dicts it is handed while renaming fields.
    """
    api = fake_ossapi(api_version)
    return api._instantiate_type(model, copy.deepcopy(payload))
