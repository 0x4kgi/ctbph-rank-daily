import argparse
import logging
import os
import re
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from ossapi import GameMode, Ossapi, Score, User
from ossapi.enums import Grade

from scripts.discord_webhook import (
    Embed,
    EmbedField,
    embed_maker,
    send_webhook,
)
from scripts.general_utils import simplify_number
from scripts.json_player_data import (
    MappedPlayerDataCollection,
    MappedScoreDataCollection,
    get_comparison_and_mapped_data,
    get_data_at_date,
    get_sorted_dict_on_stat,
    map_player_data,
)
from scripts.logging_config import setup_logging, logger

SCORE_FETCH_RETRIES = 3
SCORE_FETCH_RETRY_DELAY = 3
SCORE_FETCH_LIMIT_WARNING = 100
SUMMARY_FIELD_LIMIT = 5
NEW_ENTRIES_DISPLAY_LIMIT = 5
PP_RANKING_TOP_COUNT = 5

GRADE_EMOTES = {
    'SSH': '<:rankingXH:1247443556881399848>',
    'SS': '<:rankingX:1247443458596274278>',
    'SH': '<:rankingSH:1247443748695179315>',
    'S': '<:rankingS:1247443674862845982>',
    'A': '<:rankingA:1247443797890174986>',
    'B': '<:rankingB:1247443846900744233>',
    'C': '<:rankingC:1247443918711160874>',
    'D': '<:rankingD:1247444009010331699>',
}

ACTIVITY_WEBHOOK_USERNAME = 'Top 1k osu!catch PH tracker'
ACTIVITY_WEBHOOK_AVATAR = 'https://iili.io/JQmQKKl.png'
PP_LIST_WEBHOOK_AVATAR = 'https://iili.io/JmEwJhF.png'
ACTIVITY_FOOTER_TEXT = (
    'Updates delivered daily at around midnight. '
    'Inaccurate data? Blame Eoneru.'
)
ACTIVITY_EMBED_COLOR = 12517310
PP_EMBED_COLOR = 12891853
TOP_PLAY_EMBED_COLOR = 16775424
SITE_BASE_URL = 'https://0x4kgi.github.io/ctbph-rank-daily'

MODE_TO_GAMEMODE = {
    'osu': GameMode.OSU,
    'taiko': GameMode.TAIKO,
    'fruits': GameMode.CATCH,
    'catch': GameMode.CATCH,
    'ctb': GameMode.CATCH,
    'mania': GameMode.MANIA,
}


def resolve_game_mode(mode: str | GameMode) -> GameMode:
    if isinstance(mode, GameMode):
        return mode

    resolved_mode = MODE_TO_GAMEMODE.get(str(mode).lower())
    if resolved_mode is None:
        logger.warning(f'Unknown mode "{mode}", falling back to CATCH')
        return GameMode.CATCH

    return resolved_mode


def get_recent_plays_of_user(
    api: Ossapi,
    user_id,
    score_type: str = 'best',
    limit=5,
    mode: str | GameMode = GameMode.CATCH,
) -> list[Score]:
    logger.debug(f'recent plays: {user_id}, {score_type}, {limit}, {mode}')

    if limit > SCORE_FETCH_LIMIT_WARNING:
        logger.warning(
            f'some plays might not be gathered for this player ({user_id})'
        )

    resolved_game_mode = resolve_game_mode(mode)
    retries_left = SCORE_FETCH_RETRIES
    while retries_left > 0:
        try:
            fetched_scores = api.user_scores(
                user_id,
                score_type,
                limit=limit,
                mode=resolved_game_mode,
                include_fails=False,
            )
            logger.debug(f'# of plays: {len(fetched_scores)}')
            return fetched_scores
        except Exception as fetch_error:
            logger.error(
                f'Error on getting data for {user_id}. '
                f'Retrying in 3s. {retries_left} left ({fetch_error})'
            )
            retries_left -= 1
            time.sleep(SCORE_FETCH_RETRY_DELAY)

    logger.error(f'Cannot gather user scores for {user_id}. Returning nothing')
    return []


def get_user_info(
    api: Ossapi,
    user_id,
    mode: str | GameMode = GameMode.CATCH,
) -> User:
    return api.user(user_id, mode=resolve_game_mode(mode))


def get_emote_for_score_grade(grade: Grade | str) -> str:
    grade_name = str(grade).split('.')[-1]
    return GRADE_EMOTES.get(grade_name, '?')


def miss_format(miss) -> str:
    if miss:
        return f'{miss:,}❌'

    return '**FC 👍**'


def create_embed_from_play(
    api: Ossapi,
    play_score: Score,
    mode: str | GameMode = GameMode.CATCH,
) -> Embed:
    play_user = get_user_info(api, play_score.user_id, mode=mode)

    osu_username = play_user.username
    osu_avatar = play_user.avatar_url
    osu_url = f'https://osu.ppy.sh/users/{play_user.id}'
    user_pp = round(play_user.statistics.pp, 0)
    ph_rank = play_user.statistics.country_rank

    score_statistics = play_score.statistics
    rank_emote = get_emote_for_score_grade(play_score.rank)
    mods_text = str(play_score.mods)
    score_time = play_score.created_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    return embed_maker(
        title=play_score.beatmapset.title + (
            f' [{play_score.beatmap.version}] '
            f'[{play_score.beatmap.difficulty_rating:,.2f}★]'
        ),
        description=(
            f'**{rank_emote}** • {miss_format(score_statistics.count_miss)} '
            f'• {play_score.max_combo}x'
        ),
        fields=[
            {
                'name': 'PP',
                'value': f'{play_score.pp:,.2f}pp',
                'inline': True,
            },
            {
                'name': 'Accuracy',
                'value': f'{play_score.accuracy * 100:,.2f}%',
                'inline': True,
            },
            {
                'name': 'Mods',
                'value': mods_text,
                'inline': True,
            },
        ],
        url=str(play_score.beatmap.url),
        image={
            'url': play_score.beatmapset.covers.cover,
        },
        author={
            'name': f'{osu_username} • {user_pp:,.0f}pp • PH{ph_rank}',
            'icon_url': osu_avatar,
            'url': osu_url,
        },
        timestamp=score_time,
        color=TOP_PLAY_EMBED_COLOR,
    )


def player_profile_link(user_id) -> str:
    return f'https://osu.ppy.sh/users/{user_id}/fruits'


def format_pp_gain_line(item, latest_data, comparison_data) -> str:
    user_id = item[0]
    ign = item[1]['ign']
    gained = item[1]['pp']
    old_pp = comparison_data[user_id]['pp']
    new_pp = latest_data[user_id]['pp']
    link = player_profile_link(user_id)
    return f'1. [**{ign}**]({link}) • {old_pp:,}pp → **{new_pp:,}**pp (+**{gained:,}**pp)'


def format_rank_gain_line(item, latest_data, comparison_data) -> str:
    user_id = item[0]
    ign = item[1]['ign']
    gained = item[1]['country_rank']
    old_rank = comparison_data[user_id]['country_rank']
    new_rank = latest_data[user_id]['country_rank']
    link = player_profile_link(user_id)
    return (
        f'1. [**{ign}**]({link}) • PH{old_rank:,} → '
        f'PH**{new_rank:,}** (+**{gained:,}** ranks)'
    )


def format_play_count_line(item, latest_data, comparison_data) -> str:
    user_id = item[0]
    ign = item[1]['ign']
    gained = item[1]['play_count']
    old_count = comparison_data[user_id]['play_count']
    new_count = latest_data[user_id]['play_count']
    link = player_profile_link(user_id)
    return (
        f'1. [**{ign}**]({link}) • {old_count:,} → '
        f'{new_count:,} (+**{gained:,}** plays)'
    )


def format_ranked_score_line(item, latest_data, comparison_data) -> str:
    user_id = item[0]
    ign = item[1]['ign']
    gained = item[1]['ranked_score']
    old_score = comparison_data[user_id]['ranked_score']
    new_score = latest_data[user_id]['ranked_score']
    link = player_profile_link(user_id)
    return (
        f'1. [**{ign}**]({link}) • {simplify_number(old_score)} → '
        f'{simplify_number(new_score)} (+**{simplify_number(gained)}**)'
    )


def format_summary_field(name, ranked_data, formatter, stat, limit=5) -> EmbedField:
    ranked_items = list(ranked_data.items())[:limit]
    return {
        'name': name,
        'value': '\n'.join(
            formatter(item) for item in ranked_items if item[1][stat] > 0
        ),
    }


def create_player_summary_fields(
    pp_gainers,
    rank_gainers,
    active_players,
    ranked_score_gainers,
    latest_data,
    comparison_data,
) -> list[EmbedField]:
    pp_field = format_summary_field(
        'pp farmers', pp_gainers,
        lambda item: format_pp_gain_line(item, latest_data, comparison_data),
        'pp',
    )
    rank_field = format_summary_field(
        'PH rank climbers', rank_gainers,
        lambda item: format_rank_gain_line(item, latest_data, comparison_data),
        'country_rank',
    )
    pc_field = format_summary_field(
        '"play more" gamers', active_players,
        lambda item: format_play_count_line(item, latest_data, comparison_data),
        'play_count',
    )
    rs_field = format_summary_field(
        'ranked score farmers', ranked_score_gainers,
        lambda item: format_ranked_score_line(item, latest_data, comparison_data),
        'ranked_score',
    )

    return [pp_field, rank_field, pc_field, rs_field]


def count_positive_gains(ranked_data: dict, stat: str) -> int:
    return len([i for i in ranked_data.items() if i[1][stat] > 0])


def sum_positive_gains(ranked_data: dict, stat: str) -> int:
    return sum([ranked_data[i][stat] for i in ranked_data if ranked_data[i][stat] > 0])


def description_maker(
    active_players: dict,
    pp_gainers: dict,
    rank_gainers: dict,
    ranked_score_gainers: dict,
) -> str:
    active_count = count_positive_gains(active_players, 'play_count')
    pp_gain_count = count_positive_gains(pp_gainers, 'pp')
    rank_gain_count = count_positive_gains(rank_gainers, 'country_rank')

    total_pc = sum_positive_gains(active_players, 'play_count')
    total_pp = sum_positive_gains(pp_gainers, 'pp')
    total_rank = sum_positive_gains(rank_gainers, 'country_rank')
    total_ranked_score = simplify_number(
        sum_positive_gains(ranked_score_gainers, 'ranked_score')
    )

    # use !n for newlines
    description = """There are: **{:,}** players who played the game,
    **{:,}** players who saw pp gains,
    and **{:,}** players who climbed the PH ranks.!n!n
    In __total__ there were: **{:,}pp**,
    **{:,} ranks**,
    **{:,} play count**,
    and **{} ranked score** gained this day!""".format(
        active_count,
        pp_gain_count,
        rank_gain_count,
        total_pp,
        total_rank,
        total_pc,
        total_ranked_score,
    )

    # weird hack, i know
    description = re.sub(r'\n', ' ', description)
    description = re.sub(r'\s{4,}', ' ', description)
    description = re.sub(r'!n', '\n', description)

    return description


# noinspection PyTypedDict
def get_new_entries(data: MappedPlayerDataCollection) -> MappedPlayerDataCollection:
    return {
        i: data[i]
        for i in data
        if data[i]['new_entry']
    }


def build_new_entries_embed(new_entries, latest_mapped_data) -> Embed:
    desc_lines = []
    for user_id in new_entries:
        # /fruits should be temporary
        user_rank = latest_mapped_data[user_id]['country_rank']
        ign = new_entries[user_id]["ign"]
        desc_lines.append(
            f'- [**{ign}**](https://osu.ppy.sh/users/{user_id}/fruits) '
            f'(PH**{user_rank}**)'
        )

    if len(new_entries) > NEW_ENTRIES_DISPLAY_LIMIT:
        # limit new entries to just 5, to fit within webhook character limit
        desc_lines = desc_lines[:NEW_ENTRIES_DISPLAY_LIMIT]
        desc_lines.append(f' - *and {len(new_entries) - 5} more!*')

    full_desc = (
        'There are **{}** new peeps in the Top 1k!\nVisit [the site]('
        'https://0x4kgi.github.io/ctbph-rank-daily/) to see where they are. '
        'Try looking for ✨\n\nThey are:\n{}'
    ).format(len(new_entries), '\n'.join(desc_lines))

    return embed_maker(
        title='New players in the top 1k',
        description=full_desc,
        color=ACTIVITY_EMBED_COLOR,
    )


def send_activity_ranking_webhook(
    latest_mapped_data: dict,
    comparison_mapped_data: dict,
    data_difference: dict,
    latest_date: datetime | None = None,
) -> None:
    if latest_date is None:
        latest_date = datetime.now()

    active_players = get_sorted_dict_on_stat(data_difference, 'play_count', True)
    pp_gainers = get_sorted_dict_on_stat(data_difference, 'pp', True)
    rank_gainers = get_sorted_dict_on_stat(data_difference, 'country_rank', True)
    ranked_score_gainers = get_sorted_dict_on_stat(
        data_difference, 'ranked_score', True
    )
    new_entries = get_new_entries(data_difference)

    fields = create_player_summary_fields(
        pp_gainers=pp_gainers,
        rank_gainers=rank_gainers,
        active_players=active_players,
        ranked_score_gainers=ranked_score_gainers,
        latest_data=latest_mapped_data,
        comparison_data=comparison_mapped_data,
    )

    footer = {
        'text': ACTIVITY_FOOTER_TEXT,
    }

    embeds: list[Embed] = []

    date = latest_date.strftime('%Y-%m-%d')
    date_yesterday = latest_date - timedelta(days=1)
    yesterday_string = date_yesterday.strftime('%Y-%m-%d')

    main_embed = embed_maker(
        title='Top 5 activity rankings for {}'.format(
            latest_date.strftime('%B %d, %Y')
        ),
        url=f'{SITE_BASE_URL}/activity-ranking.html#start:{yesterday_string};end:{date}',
        description=description_maker(
            active_players,
            pp_gainers,
            rank_gainers,
            ranked_score_gainers,
        ),
        fields=fields,
        footer=footer,
        color=ACTIVITY_EMBED_COLOR,
    )
    embeds.append(main_embed)

    if len(new_entries) > 0:
        embeds.append(build_new_entries_embed(new_entries, latest_mapped_data))

    send_webhook(
        content='``` ```',
        embeds=embeds,
        username=ACTIVITY_WEBHOOK_USERNAME,
        avatar_url=ACTIVITY_WEBHOOK_AVATAR,
    )


def format_pp_record_line(index: int, score: Score) -> str:
    # 1. {pp}pp - Player
    player_info = '***{}.*** **{:,.2f}**pp • **{}**'.format(
        index + 1,
        score.pp,
        score._user.username,
    )

    # map name and link also mod?
    map_info = '` ` [**{} [{}]** [{:,.2f}★]]({}) +{}'.format(
        score.beatmapset.title,
        score.beatmap.version,
        score.beatmap.difficulty_rating,
        score.beatmap.url,
        score.mods,
    )

    # score statistics
    score_statistics = '` ` {} / {:,.2f}% / {} / {:,}x\n'.format(
        get_emote_for_score_grade(score.rank),
        score.accuracy * 100,
        miss_format(score.statistics.count_miss),
        score.max_combo,
    )

    return '\n'.join([player_info, map_info, score_statistics])


def create_pp_record_list_embed(scores: list[Score]) -> Embed:
    description: str = 'Visit the link above for the top 100. Might be incomplete.\n\n'

    for index, score in enumerate(scores):
        description += format_pp_record_line(index, score)

    date = datetime.now().strftime('%Y-%m-%d')

    return embed_maker(
        title=f'Top 5 pp records for {date}',
        url=f'{SITE_BASE_URL}/pp-rankings.html#date:{date}',
        description=description,
        color=PP_EMBED_COLOR,
        footer={
            'text': 'Only ranked submitted plays.'
        },
    )


def fetch_top_scores(api: Ossapi, mapped_scores, mode: str, top: int) -> list[Score]:
    resolved_game_mode = resolve_game_mode(mode)
    fetched_scores: list[Score] = []
    for score_id, score_data in list(mapped_scores.items())[:top]:
        if score_data['score_type'] == 'old':
            score = api.score_mode(resolved_game_mode, score_id)
        else:
            score = api.score(score_id)

        fetched_scores.append(score)

    return fetched_scores


def send_play_pp_ranking_webhook(
    api: Ossapi,
    latest_timestamp: datetime,
    mode: str,
    country: str,
    test: bool,
    top: int = PP_RANKING_TOP_COUNT,
) -> None:
    # Get the pp scores from file
    raw_scores = get_data_at_date(
        date=latest_timestamp.strftime('%Y/%m/%d'),
        country=country,
        mode=mode,
        file_type='pp-records',
        test=test,
    )

    if raw_scores is None:
        logger.warning('Cannot get pp score list at the moment.')
        return

    # Map the scores to a dict
    mapped_scores: MappedScoreDataCollection = map_player_data(raw_scores)

    # get the top 5 only and convert each to a Score object
    # then append to a Score list
    scores = fetch_top_scores(api, mapped_scores, mode, top)

    # end early if no scores are to be found
    if len(scores) == 0:
        logger.warning('No scores to be listed. :(')
        return

    # make the list of the top 10 as a separate webhook
    pp_list_embed = create_pp_record_list_embed(scores)
    send_webhook(
        username=f'top {top} pp records of the day',
        embeds=[pp_list_embed],
        avatar_url=PP_LIST_WEBHOOK_AVATAR,
    )

    # send the highest pp play
    top_pp_embed = create_embed_from_play(api, scores[0], mode=mode)
    send_webhook(
        username='pp record of the day',
        embeds=[top_pp_embed],
        avatar_url=PP_LIST_WEBHOOK_AVATAR,
    )


def main(country: str = 'PH', mode: str = 'fruits', test: bool = False):
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')
    # noinspection PyTypeChecker
    api = Ossapi(client_id, client_secret)

    latest_date = datetime.now()
    processed_data = get_comparison_and_mapped_data(
        base_date=latest_date,
        compare_date_offset=1,
        country=country,
        mode=mode,
        test=test,
    )
    latest_mapped_data = processed_data.latest_mapped_data
    comparison_mapped_data = processed_data.comparison_mapped_data
    data_difference = processed_data.data_difference

    if latest_mapped_data is None:
        logger.warning('Cannot get latest data as of now.')
        return

    if comparison_mapped_data is None:
        logger.warning('Cannot get comparison data as of now.')
        return

    logger.info('Making the activity webhook')
    send_activity_ranking_webhook(
        latest_mapped_data=latest_mapped_data,
        comparison_mapped_data=comparison_mapped_data,
        data_difference=data_difference,
        latest_date=latest_date,
    )

    logger.info('Making the pp related webhook')
    send_play_pp_ranking_webhook(
        api=api,
        latest_timestamp=latest_date,
        mode=mode,
        country=country,
        test=test,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Send a Discord webhook message from fetched data, '
                    'requires leaderboard_scrape.py to be ran first!'
    )

    parser.add_argument(
        '--mode', type=str, default='fruits',
        help='Define what mode, uses the parameters used on osu site.',
    )
    parser.add_argument(
        '--country', type=str, default='PH',
        help='What country to make a webhook message from. '
             'Uses 2 letter country codes.',
    )
    parser.add_argument('--test', action='store_true', help='Just do tests')

    args = parser.parse_args()

    if args.test:
        setup_logging(level=logging.DEBUG)
    else:
        setup_logging()

    load_dotenv()

    main(
        country=args.country,
        mode=args.mode,
        test=args.test,
    )
