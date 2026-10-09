import argparse
import json
import logging
import os
import re
import time
from datetime import datetime

from dotenv import load_dotenv
from ossapi import Ossapi, GameMode, RankingType, Score, models

from scripts.json_player_data import (
    MappedPlayerData,
    MappedScoreData,
    RawPlayerDataCollection,
    get_comparison_and_mapped_data,
    get_sorted_dict_on_stat,
)
from scripts.logging_config import setup_logging, logger
from send_discord_webhook import get_recent_plays_of_user

MAX_RANKING_PAGES = 200
RANKING_FILE_VERSION = 1.01
PP_RECORDS_FILE_VERSION = 1.011
PAGE_FETCH_RETRIES = 3
PAGE_FETCH_RETRY_DELAY = 3
PP_RECORDS_TOP_COUNT = 100
OLD_SCORE_ID_LENGTH_THRESHOLD = 10

PLAYER_VALUE_MAPPING = [
    'country_rank',
    'global_rank',
    'ign',
    'pp',
    'acc',
    'play_count',
    'rank_x',
    'rank_s',
    'rank_a',
    'play_time',
    'total_score',
    'ranked_score',
    'total_hits',
]
PLAYER_VALUES_KEY = 'id'

SCORE_VALUE_MAPPING = [
    'score_type',
    'score_mods',
    'score_pp',
    'score_grade',
    'user_id',
    'user_name',
    'beatmapset_title',
    'beatmap_version',
    'beatmap_id',
    'beatmapset_id',
    'beatmap_difficulty',
    'full_combo',
    'max_combo',
    'count_300',
    'count_100',
    'count_50',
    'count_droplet_miss',
    'count_miss',
    'accuracy',
]
SCORE_VALUES_KEY = 'score_id'

MODE_ALIASES = {
    '0': 'osu', 'osu': 'osu', 'std': 'osu', 'standard': 'osu', 's': 'osu',
    '1': 'taiko', 'taiko': 'taiko', 'taco': 'taiko', 't': 'taiko',
    '2': 'fruits', 'ctb': 'fruits', 'fruits': 'fruits', 'catch': 'fruits',
    'c': 'fruits',
    '3': 'mania', 'mania': 'mania', 'm': 'mania',
}


def resolve_mode(mode_arg: str) -> str | None:
    return MODE_ALIASES.get(mode_arg)


def encode_to_map(
    key_mapping: list[str],
    row_data: dict[str, str],
    key_field: str,
) -> tuple[str, list[any]]:
    return row_data[key_field], [row_data[column] for column in key_mapping]


def format_data_from_rows(rows: models.Rankings) -> list[MappedPlayerData]:
    mapped_rows: list[MappedPlayerData] = []

    for ranking_row in rows.ranking:
        mapped_rows.append({
            'country_rank': ranking_row.country_rank,
            'global_rank': ranking_row.global_rank,
            'id': ranking_row.user.id,
            'ign': ranking_row.user.username,
            'pp': int(round(ranking_row.pp)),
            'acc': ranking_row.hit_accuracy,
            'play_count': ranking_row.play_count,
            'rank_x': ranking_row.grade_counts.ss + ranking_row.grade_counts.ssh,
            'rank_s': ranking_row.grade_counts.s + ranking_row.grade_counts.sh,
            'rank_a': ranking_row.grade_counts.a,
            'play_time': ranking_row.play_time,
            'total_score': ranking_row.total_score,
            'ranked_score': ranking_row.ranked_score,
            'total_hits': ranking_row.total_hits,
        })

    return mapped_rows


def get_page_rankings(
    page: int = 1,
    mode: str = GameMode.CATCH,
    country: str = None,
) -> list[MappedPlayerData]:
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')

    # noinspection PyTypeChecker
    api = Ossapi(client_id, client_secret)

    retries_left = PAGE_FETCH_RETRIES
    while retries_left > 0:
        try:
            # noinspection PyTypeChecker
            ranking_response = api.ranking(
                mode, RankingType.PERFORMANCE,
                country=country, cursor={'page': page},
            )
            return format_data_from_rows(ranking_response)
        except Exception as fetch_error:
            logger.error(
                f'Error on getting data for {country}-{mode} page {page}. '
                f'Retrying in 3s. {retries_left} left ({fetch_error})'
            )
            retries_left -= 1
            time.sleep(PAGE_FETCH_RETRY_DELAY)

    logger.error(
        f'Unable to get data for {country}-{mode} page {page}. Returning nothing.'
    )
    return []


def get_rankings(
    mode: str = 'osu',
    country: str = None,
    pages: int = 1,
) -> RawPlayerDataCollection:
    pages = min(pages, MAX_RANKING_PAGES)

    full_data: RawPlayerDataCollection = {
        # INFO: increment by one every time you change the format of the
        #       resulting json file and change data/file_versions.json too
        'file_version': RANKING_FILE_VERSION,
        'file_type': 'rankings',
        'update_date': time.time(),
        'mode': mode,
        'country': country if country else 'all',
        'pages': pages,
        'map': PLAYER_VALUE_MAPPING,
        'key': PLAYER_VALUES_KEY,
        'data': {},
    }

    for page_index in range(int(pages)):
        fetch_start_time = time.time()

        page_rows = get_page_rankings(page_index + 1, mode, country)

        if len(page_rows) == 0:
            logger.warning(f'Data for {country}-{mode} page {page_index} is nothing!')
            continue

        for player_row in page_rows:
            player_id, player_values = encode_to_map(
                PLAYER_VALUE_MAPPING, player_row, PLAYER_VALUES_KEY
            )
            full_data['data'][player_id] = player_values

        fetch_duration = time.time() - fetch_start_time
        logger.info(
            f'c: {country} m: {mode} c/f: {page_index + 1}/{pages} '
            f'OK: {fetch_duration:.4f}s'
        )

    return full_data


def dump_to_file(
    data: RawPlayerDataCollection,
    test: bool = False,
    formatted: bool = False,
) -> str:
    mode = data.get('mode', None)
    country = data.get('country', None)

    if mode is None or country is None:
        logger.warning('mode or country is None')

    # Rankings payloads carry 'file_type' while pp-records payloads carry
    # 'type'. Only 'type' produces a filename suffix, which keeps ranking
    # files at PH-fruits.json instead of PH-fruits-rankings.json.
    file_type = data.get('type', None)

    today = datetime.now()
    date_string = today.strftime('%Y/%m/%d')

    output = json.dumps(data, separators=(',', ':'), indent=0 if formatted else None)

    if formatted:
        output = re.sub(r'(\d"):\[\s+', r'\1:[', output)
        output = re.sub(r'("|\w),\s+', r'\1,', output)
        output = re.sub(r'(\d)\s+\]', r'\1]', output)

    if file_type:
        output_file = f'docs/data/{date_string}/{country}-{mode}-{file_type}.json'
    else:
        output_file = f'docs/data/{date_string}/{country}-{mode}.json'

    if test:
        output_file = 'tests/' + output_file

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as json_file:
        json_file.write(output)

    return output_file


def format_score_data_from_list(scores: list[Score]) -> list[MappedScoreData]:
    if len(scores) == 0:
        return []

    mapped_scores = []

    for score in scores:
        mapped_scores.append({
            'score_id': score.id,
            'score_type': (
                'old' if len(str(score.id)) < OLD_SCORE_ID_LENGTH_THRESHOLD else 'new'
            ),
            'score_mods': str(score.mods),
            'score_pp': score.pp,
            'score_grade': str(score.rank).split('.')[-1],

            'user_id': score.user_id,
            'user_name': score._user.username,

            'beatmapset_title': score.beatmapset.title,
            'beatmap_version': score.beatmap.version,
            'beatmap_id': score.beatmap.id,
            'beatmapset_id': score.beatmapset.id,
            'beatmap_difficulty': score.beatmap.difficulty_rating,

            'full_combo': score.perfect,
            'max_combo': score.max_combo,
            'count_300': score.statistics.count_300,
            'count_100': score.statistics.count_100,
            'count_50': score.statistics.count_50,
            'count_droplet_miss': score.statistics.count_katu,
            'count_miss': score.statistics.count_miss,
            'accuracy': score.accuracy,
        })

    return mapped_scores


def sort_scores_by_pp(
    scores: list[Score],
    top: int = 10,
    min_date: float = 0,
    max_date: float = datetime.now().timestamp(),
) -> list[Score]:
    def is_score_in_range(score: Score) -> bool:
        if score.pp is None:
            return False

        score_timestamp = score.created_at.timestamp()
        if score_timestamp < min_date:
            return False
        if score_timestamp > max_date:
            return False
        return True

    filtered_scores = [score for score in scores if is_score_in_range(score)]

    return sorted(filtered_scores, key=lambda s: s.pp, reverse=True)[:top]


def remove_duplicate_scores(scores: list[Score]) -> list[Score]:
    best_scores: dict = {}

    for score in scores:
        if score.pp is None:
            continue

        dedupe_key = (
            score._user.id,
            score.beatmap.id,
            score.beatmapset.id,
        )
        if dedupe_key not in best_scores or score.pp > best_scores[dedupe_key].pp:
            logger.debug(
                f'{score._user.username} has a better score on '
                f'{score.beatmapset.title} [{score.beatmap.version}] '
                f'with {score.pp}'
            )
            best_scores[dedupe_key] = score

    return list(best_scores.values())


def get_pp_plays(
    mode: str = 'fruits',
    country: str = 'PH',
    test: bool = False,
) -> RawPlayerDataCollection | None:
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')
    # noinspection PyTypeChecker
    api = Ossapi(client_id, client_secret)

    processed_data = get_comparison_and_mapped_data(
        base_date=datetime.now(),
        compare_date_offset=1,
        country=country,
        mode=mode,
        test=test,
    )

    if processed_data.latest_mapped_data is None:
        logger.info('No latest data for comparison')
        return None
    if processed_data.comparison_mapped_data is None:
        logger.info('No old data for comparison')
        return None

    active_players = get_sorted_dict_on_stat(
        data=processed_data.data_difference,
        stat='play_count',
        highest_first=True,
    )

    gathered_scores: list[Score] = []

    for user_id in active_players:
        # noinspection PyTypedDict
        logger.debug(f"Fetching scores for {active_players[user_id]['ign']}...")

        # noinspection PyTypedDict
        user_scores = get_recent_plays_of_user(
            api=api,
            user_id=user_id,
            score_type='recent',
            limit=active_players[user_id]['play_count'],
        )
        gathered_scores += user_scores

    gathered_scores = remove_duplicate_scores(gathered_scores)
    gathered_scores = sort_scores_by_pp(gathered_scores, top=PP_RECORDS_TOP_COUNT)
    formatted_list = format_score_data_from_list(gathered_scores)

    full_data: RawPlayerDataCollection = {
        'file_version': PP_RECORDS_FILE_VERSION,
        'update_date': time.time(),
        'type': 'pp-records',
        'mode': mode,
        'country': country if country else 'all',
        'map': SCORE_VALUE_MAPPING,
        'key': SCORE_VALUES_KEY,
        'data': {},
    }

    for mapped_score in formatted_list:
        score_id, score_values = encode_to_map(
            SCORE_VALUE_MAPPING, mapped_score, SCORE_VALUES_KEY
        )
        full_data['data'][score_id] = score_values

    return full_data


def run(
    mode: str = 'fruits',
    country: str = 'PH',
    pages: int = 20,
    formatted: bool = False,
    test: bool = False,
    skip_pp_plays: bool = False,
    skip_rankings: bool = False,
) -> None:
    logger.info(f'running main method, {skip_pp_plays=} {skip_rankings=}')

    if not skip_rankings:
        ranking_data = get_rankings(mode=mode, country=country, pages=pages)
        ranking_file = dump_to_file(data=ranking_data, test=test, formatted=formatted)
        logger.info(msg=f'Ranking json created at: {ranking_file}')
    else:
        logger.info('Skipping gathering of rankings')

    if skip_pp_plays:
        logger.info('Skipping gathering of pp plays')
        return

    pp_data = get_pp_plays(mode=mode, country=country, test=test)

    if pp_data is None:
        logger.info('Incomplete data for pp listing, skipping gathering of pp plays')
        return

    pp_file = dump_to_file(data=pp_data, test=test, formatted=formatted)
    logger.info(msg=f'pp plays json created at: {pp_file}')


if __name__ == '__main__':
    load_dotenv()

    parser = argparse.ArgumentParser(
        description='Gets the leaderboard for a mode and country. Via web scraping'
    )

    parser.add_argument(
        '-m', '--mode', type=str, default='2',
        help="What game mode to scan for. You can use owo bot's -m params or "
             'short hands like ctb, std, etc.',
    )
    parser.add_argument(
        '-p', '--pages', type=int, default=20,
        help='Number of pages to scan, maximum of 200. Defaults to 1',
    )
    parser.add_argument(
        '-c', '--country', type=str, default='PH',
        help="What country's leaderboard to scan for. "
             'Uses the 2 letter system (US, JP, PH, etc.)',
    )
    parser.add_argument('--test', action='store_true', help='Just do tests')
    parser.add_argument(
        '--formatted', action='store_true',
        help='Make the output .json to be somewhat readable',
    )
    parser.add_argument(
        '--skip-pp-plays', action='store_true',
        help='Do not try to gather top pp plays.',
    )
    parser.add_argument(
        '--skip-rankings', action='store_true',
        help='Skip gathering leaderboard rankings.',
    )

    args = parser.parse_args()

    if args.test:
        setup_logging(level=logging.DEBUG)
    else:
        setup_logging()

    resolved_mode = resolve_mode(args.mode)
    if resolved_mode is None:
        logger.warning(f'This mode: "{args.mode}" is not a valid one. Try again')
        exit()

    run(
        mode=resolved_mode,
        country=args.country,
        pages=args.pages,
        formatted=args.formatted,
        test=args.test,
        skip_pp_plays=args.skip_pp_plays,
        skip_rankings=args.skip_rankings,
    )
