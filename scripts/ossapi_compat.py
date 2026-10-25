"""Translate ossapi's modern score models into this project's legacy schema.

osu! changed the score object at ``x-api-version: 20220705``: ``created_at``
became ``ended_at``, ``perfect`` split into ``legacy_perfect`` and
``is_perfect_combo``, ``mods`` became a list of objects, and statistics use
lazer hit-result names. Everything under ``docs/data/`` (and the site and
Discord embeds reading it) uses the old shape, so scores are translated here
instead of pinning the API back to the old response format.

Field mapping follows osu-web's ``SoloScore::makeLegacyEntry()``.
"""
from ossapi import GameMode

# ossapi 5.3.6 is written against this response version. Pinning it keeps the
# models we deserialize stable even if the library changes its default.
OSU_API_VERSION = 20241024

MODE_ALIASES = {
    'osu': 'osu',
    'std': 'osu',
    'standard': 'osu',
    'taiko': 'taiko',
    'fruits': 'fruits',
    'catch': 'fruits',
    'ctb': 'fruits',
    'mania': 'mania',
}

# legacy count field -> modern statistic field, per ruleset.
RULESET_STATISTICS = {
    'osu': {
        'count_300': 'great',
        'count_100': 'ok',
        'count_50': 'meh',
    },
    'taiko': {
        'count_300': 'great',
        'count_100': 'ok',
    },
    'fruits': {
        'count_300': 'great',
        'count_100': 'large_tick_hit',
        'count_50': 'small_tick_hit',
        'count_katu': 'small_tick_miss',
    },
    'mania': {
        'count_300': 'great',
        'count_100': 'ok',
        'count_50': 'meh',
        'count_katu': 'good',
    },
}


def _ruleset_name(mode: str | GameMode) -> str:
    if isinstance(mode, GameMode):
        return mode.value

    mode_name = str(mode).lower()
    return MODE_ALIASES.get(mode_name, mode_name)


def _count(value) -> int:
    # The api omits zero-valued statistics, and old responses returned 0.
    return 0 if value is None else int(value)


def has_legacy_score_id(score) -> bool:
    """Whether the score was set in stable and has an old-scheme id."""
    return getattr(score, 'legacy_score_id', None) is not None


def score_reference_id(score) -> int:
    """The id used to link to and re-fetch this score."""
    reference_id = (
        score.legacy_score_id if has_legacy_score_id(score) else score.id
    )
    if reference_id is None:
        raise RuntimeError(
            'score has neither legacy_score_id nor id, so it cannot be '
            f'referenced (api_version={OSU_API_VERSION})'
        )

    return reference_id


def score_created_at(score):
    """Legacy ``created_at``, translated from ``ended_at``."""
    ended_at = getattr(score, 'ended_at', None)
    if ended_at is None:
        raise RuntimeError(
            'score has no ended_at, so created_at cannot be translated '
            f'(api_version={OSU_API_VERSION}); did the osu! score model '
            'change?'
        )

    return ended_at


def score_mods_text(score) -> str:
    """Legacy mod string, e.g. ``HDHR``."""
    acronyms = [mod.acronym for mod in score.mods]

    # CL (Classic) only exists on lazer submissions; stable scores never had
    # it, and osu!'s legacy response never returned it.
    if has_legacy_score_id(score):
        acronyms = [acronym for acronym in acronyms if acronym != 'CL']

    return ''.join(acronyms) or 'NM'


def score_full_combo(score) -> bool:
    """Legacy ``perfect``: stable logic for stable, lazer logic for lazer."""
    if has_legacy_score_id(score):
        preferred_field, fallback_field = (
            'legacy_perfect', 'is_perfect_combo',
        )
    else:
        preferred_field, fallback_field = (
            'is_perfect_combo', 'legacy_perfect',
        )

    full_combo = getattr(score, preferred_field, None)
    if full_combo is None:
        full_combo = getattr(score, fallback_field, False)

    return bool(full_combo)


def score_miss_count(score) -> int:
    return _count(getattr(score.statistics, 'miss', None))


def score_user_name(
    score,
    user_names: dict[int, str] | None = None,
) -> str:
    """Username for a score, without relying on the deprecated user include.

    osu! deprecated ``user`` in Get User Scores responses. Callers which
    already know the name (rankings file, stored pp-records row) pass a
    ``user_id -> username`` map so this keeps working if it goes away.
    """
    if user_names is not None:
        user_name = user_names.get(score.user_id)
        if user_name is not None:
            return user_name

    user = getattr(score, '_user', None)
    if user is not None:
        return user.username

    return f'user {score.user_id}'


def score_judgement_counts(
    score,
    mode: str | GameMode,
) -> dict[str, int | None]:
    """Legacy ``count_*`` statistics for the given mode.

    Fields the mode does not have are omitted, matching the api's nulls.
    """
    ruleset = _ruleset_name(mode)
    statistic_fields = RULESET_STATISTICS.get(ruleset)
    if statistic_fields is None:
        raise ValueError(
            f'unsupported mode for score translation: {mode!r}'
        )

    statistics = score.statistics
    counts = {
        legacy_name: _count(getattr(statistics, modern_name, None))
        for legacy_name, modern_name in statistic_fields.items()
    }
    counts['count_miss'] = _count(getattr(statistics, 'miss', None))

    return counts
