"""Recorded osu! API payloads and a real-model loader for tests.

Payloads were captured from the live v2 API on 2026-10-25 at
``x-api-version: 20241024`` and trimmed to the fields this project reads.
``parse_model`` runs the same deserialization path as ``Ossapi._request``
(without OAuth or network), so these tests fail if ossapi changes a model
shape. The SimpleNamespace fakes in the other test modules cannot catch that.
"""
import copy
import logging

from ossapi import Ossapi

# Shared by both payloads: /scores/fruits/{id} responses.
_COMMON_KEYS = {
    "best_id": None,
    "classic_total_score": 26000000,
    "current_user_attributes": {},
    "has_replay": False,
    "passed": True,
    "preserve": False,
    "processed": True,
    "ranked": True,
    "replay": False,
    "ruleset_id": 2,
    "started_at": None,
    "total_score_without_mods": 20000000,
    "type": "solo_score",
}

# Stable (osu!stable) score: legacy_score_id is present, mods include CL.
STABLE_SCORE_PAYLOAD = {
    **_COMMON_KEYS,
    "id": 7653394134,
    "legacy_score_id": 225335112,
    "legacy_total_score": 26000000,
    "legacy_perfect": True,
    "is_perfect_combo": True,
    "user_id": 1626093,
    "accuracy": 0.997537,
    "max_combo": 751,
    "pp": 544.464,
    "rank": "SH",
    "mods": [{"acronym": "HR"}, {"acronym": "HD"}, {"acronym": "CL"}],
    "ended_at": "2026-10-08T16:45:15Z",
    "statistics": {
        "great": 745,
        "large_tick_hit": 6,
        "small_tick_hit": 59,
        "small_tick_miss": 2,
    },
    "maximum_statistics": {"great": 745},
    "beatmap_id": 5882157,
    "total_score": 26000000,
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
    "user": {"id": 1626093, "username": "Maririn"},
}

# osu!lazer-only score: no legacy_score_id, so no CL filtering and the modern
# id is used for links. Mods are overridden in tests that need CL.
LAZER_SCORE_PAYLOAD = {
    **_COMMON_KEYS,
    "id": 7764291310,
    "legacy_score_id": None,
    "legacy_total_score": 0,
    "legacy_perfect": False,
    "is_perfect_combo": False,
    "user_id": 38197538,
    "accuracy": 0.94957,
    "max_combo": 84,
    "pp": 8.0315,
    "rank": "A",
    "mods": [],
    "ended_at": "2026-10-25T06:26:54Z",
    "statistics": {
        "miss": 23,
        "great": 462,
        "ignore_miss": 186,
        "large_bonus": 5,
        "small_tick_hit": 310,
        "small_tick_miss": 18,
    },
    "maximum_statistics": {"great": 462},
    "beatmap_id": 916931,
    "total_score": 26000000,
    "beatmap": {
        "id": 916931,
        "version": "Tt's Hard",
        "difficulty_rating": 1.94943,
        "url": "https://osu.ppy.sh/beatmaps/916931",
    },
    "beatmapset": {
        "id": 423500,
        "title": "Melissa (TV size ver.)",
        "covers": {
            "cover": "https://assets.ppy.sh/beatmaps/423500/covers/cover.jpg",
        },
    },
    "user": {"id": 38197538, "username": "F1orence"},
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
