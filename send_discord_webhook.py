import argparse
import logging
import math
import os
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


def get_recent_plays_of_user(api: Ossapi, user_id, score_type: str = 'best', limit=5) -> list[Score]:
    logger.debug(f'recent plays: {user_id}, {score_type}, {limit}')

    if limit > 100:
        logger.warning(f'some plays might not be gathered for this player ({user_id})')

    retries = 3
    while retries > 0:
        try:
            data = api.user_scores(
                user_id,
                score_type,
                limit=limit,
                mode=GameMode.CATCH,
                include_fails=False
            )
            logger.debug(f'# of plays: {len(data)}')
            return data
        except:
            logger.error(f'Error on getting data for {user_id}. Retrying in 3s. {retries} left')
            retries -= 1
            time.sleep(3)

    logger.error(f'Cannot gather user scores for {user_id}. Returning nothing')
    return []


def get_user_info(api: Ossapi, user_id) -> User:
    return api.user(user_id, mode=GameMode.CATCH)


def get_emote_for_score_grade(grade: Grade | str) -> str:
    ranks_dict = {
        'SSH': '<:rankingXH:1247443556881399848>',
        'SS': '<:rankingX:1247443458596274278>',
        'SH': '<:rankingSH:1247443748695179315>',
        'S': '<:rankingS:1247443674862845982>',
        'A': '<:rankingA:1247443797890174986>',
        'B': '<:rankingB:1247443846900744233>',
        'C': '<:rankingC:1247443918711160874>',
        'D': '<:rankingD:1247444009010331699>',
    }
    grade = str(grade).split('.')[-1]
    return ranks_dict.get(grade, '?')


def create_embed_from_play(api: Ossapi, data: Score) -> Embed:
    user = get_user_info(api, data.user_id)

    osu_username = user.username
    osu_avatar = user.avatar_url
    osu_url = f'https://osu.ppy.sh/users/{user.id}'
    user_pp = round(user.statistics.pp, 0)
    ph_rank = user.statistics.country_rank

    score = data.statistics
    max_combo = data.max_combo
    rank = get_emote_for_score_grade(data.rank)
    mods = str(data.mods)
    score_time = data.created_at.strftime('%Y-%m-%dT%H:%m:%S.%fZ')

    embed_data = embed_maker(
        title=data.beatmapset.title + f' [{data.beatmap.version}] [{data.beatmap.difficulty_rating:,.2f}★]',
        description=f'**{rank}** • {miss_format(score.count_miss)} • {max_combo}x',
        fields=[
            {
                'name': 'PP',
                'value': f'{data.pp:,.2f}pp',
                'inline': True
            },
            {
                'name': 'Accuracy',
                'value': f'{data.accuracy * 100:,.2f}%',
                'inline': True
            },
            {
                'name': 'Mods',
                'value': mods,
                'inline': True
            },
        ],
        url=str(data.beatmap.url),
        image={
            'url': data.beatmapset.covers.cover
        },
        author={
            'name': f'{osu_username} • {user_pp:,.0f}pp • PH{ph_rank}',
            'icon_url': osu_avatar,
            'url': osu_url,
        },
        timestamp=score_time,
        color=16775424,
    )

    return embed_data


# TODO: clean the parameters to avoid adding another one if more stats are shown
def create_player_summary_fields(
        pp_gainers,
        rank_gainers,
        active_players,
        ranked_score_gainers,
        latest_data,
        comparison_data
) -> list[EmbedField]:
    def format_field(name, data, formatter, stat, limit=5) -> EmbedField:
        return {
            'name': name,
            'value': '\n'.join(
                formatter(item) for item in list(data.items())[:limit] if item[1][stat] > 0
            )
        }

    def _uid_link(item):
        return item[0], f'https://osu.ppy.sh/users/{item[0]}/fruits'

    def _get_stats(uid, stat):
        nonlocal latest_data, comparison_data
        old = comparison_data[uid][stat]
        new = latest_data[uid][stat]
        return old, new

    # TODO: maybe reduce code repetition here, on the formatters
    def pp_formatter(item):
        uid, link = _uid_link(item)
        ign = item[1]['ign']
        gained = item[1]['pp']
        old, new = _get_stats(uid, 'pp')
        return f'1. [**{ign}**]({link}) • {old:,}pp → **{new:,}**pp (+**{gained:,}**pp)'

    def rank_formatter(item):
        uid, link = _uid_link(item)
        ign = item[1]['ign']
        gained = item[1]['country_rank']
        old, new = _get_stats(uid, 'country_rank')
        return f'1. [**{ign}**]({link}) • PH{old:,} → PH**{new:,}** (+**{gained:,}** ranks)'

    def pc_formatter(item):
        uid, link = _uid_link(item)
        ign = item[1]['ign']
        gained = item[1]['play_count']
        old, new = _get_stats(uid, 'play_count')
        return f'1. [**{ign}**]({link}) • {old:,} → {new:,} (+**{gained:,}** plays)'

    def rs_formatter(item):
        uid, link = _uid_link(item)
        ign = item[1]['ign']
        gained = item[1]['ranked_score']
        old, new = _get_stats(uid, 'ranked_score')
        return f'1. [**{ign}**]({link}) • {simplify_number(old)} → {simplify_number(new)} (+**{simplify_number(gained)}**)'

    # this is getting ugly, man
    pp_field = format_field('pp farmers', pp_gainers, pp_formatter, 'pp')
    rank_field = format_field('PH rank climbers', rank_gainers, rank_formatter, 'country_rank')
    pc_field = format_field('"play more" gamers', active_players, pc_formatter, 'play_count')
    rs_field = format_field('ranked score farmers', ranked_score_gainers, rs_formatter, 'ranked_score')

    return [pp_field, rank_field, pc_field, rs_field]


def description_maker(
        active_players: dict,
        pp_gainers: dict,
        rank_gainers: dict,
        ranked_score_gainers: dict,
) -> str:
    import re

    def above_zero_count(data: dict, key: str) -> int:
        return len([i for i in data.items() if i[1][key] > 0])

    def total_stat(data, key) -> int:
        return sum([data[i][key] for i in data if data[i][key] > 0])

    # TODO: maybe clean this up too, but this is nothing major anyway
    active_count = above_zero_count(active_players, 'play_count')
    pp_gain_count = above_zero_count(pp_gainers, 'pp')
    rank_gain_count = above_zero_count(rank_gainers, 'country_rank')

    total_pc = total_stat(active_players, 'play_count')
    total_pp = total_stat(pp_gainers, 'pp')
    total_rank = total_stat(rank_gainers, 'country_rank')
    total_ranked_score = simplify_number(total_stat(ranked_score_gainers, 'ranked_score'))

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


def send_activity_ranking_webhook(
        latest_mapped_data: dict,
        comparison_mapped_data: dict,
        data_difference: dict,
        latest_date: datetime = datetime.now(),
) -> None:
    # TODO: this is getting ridiculous, find a way to simplify this
    active_players = get_sorted_dict_on_stat(data_difference, 'play_count', True)
    pp_gainers = get_sorted_dict_on_stat(data_difference, 'pp', True)
    rank_gainers = get_sorted_dict_on_stat(data_difference, 'country_rank', True)
    ranked_score_gainers = get_sorted_dict_on_stat(data_difference, 'ranked_score', True)
    new_entries = get_new_entries(data_difference)

    # TODO: clean this up, please holy fuck
    fields = create_player_summary_fields(
        pp_gainers=pp_gainers,
        rank_gainers=rank_gainers,
        active_players=active_players,
        ranked_score_gainers=ranked_score_gainers,
        latest_data=latest_mapped_data,
        comparison_data=comparison_mapped_data
    )

    footer = {
        'text': 'Updates delivered daily at around midnight. Inaccurate data? Blame Eoneru.',
    }

    embeds: list[Embed] = []

    date = latest_date.strftime('%Y-%m-%d')
    date_yesterday = latest_date - timedelta(days=1)
    dy_frmt = date_yesterday.strftime('%Y-%m-%d')

    main_embed = embed_maker(
        title='Top 5 activity rankings for {}'.format(latest_date.strftime('%B %d, %Y')),
        url=f'https://0x4kgi.github.io/ctbph-rank-daily/activity-ranking.html#start:{dy_frmt};end:{date}',
        description=description_maker(
            active_players,
            pp_gainers,
            rank_gainers,
            ranked_score_gainers
        ),
        fields=fields,
        footer=footer,
        color=12517310
    )
    embeds.append(main_embed)

    if len(new_entries) > 0:
        desc = []
        for user_id in new_entries:
            # /fruits should be temporary
            user_info = latest_mapped_data[user_id]
            user_rank = user_info['country_rank']
            desc.append(f'- [**{new_entries[user_id]['ign']}**](https://osu.ppy.sh/users/{user_id}/fruits) (PH**{user_rank}**)')

        if len(new_entries) > 5:
            # limit new entries to just 5, to fit within webhook character limit
            desc = desc[:5]
            desc.append(f' - *and {len(new_entries) - 5} more!*')

        full_desc = ('There are **{}** new peeps in the Top 1k!\nVisit [the site]('
                     'https://0x4kgi.github.io/ctbph-rank-daily/) to see where they are. Try looking for ✨\n\nThey '
                     'are:\n{}').format(
            len(new_entries),
            '\n'.join(desc)
        )

        embeds.append(embed_maker(
            title='New players in the top 1k',
            description=full_desc,
            color=12517310,
        ))

    send_webhook(
        content='``` ```',
        embeds=embeds,
        username='Top 1k osu!catch PH tracker',
        avatar_url='https://iili.io/JQmQKKl.png'
    )


def miss_format(miss) -> str:
    if miss:
        return f'{miss:,}❌'
    else:
        return '**FC 👍**'


def create_pp_record_list_embed(scores: list[Score]) -> Embed:
    def formatter(index: int, score: Score) -> str:

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

    description: str = 'Visit the link above for the top 100. Might be incomplete.\n\n'

    for index, scr in enumerate(scores):
        description += formatter(index, scr)

    date = datetime.now().strftime('%Y-%m-%d')

    return embed_maker(
        title=f'Top 5 pp records for {date}',
        url=f'https://0x4kgi.github.io/ctbph-rank-daily/pp-rankings.html#date:{date}',
        description=description,
        color=12891853,
        footer={
            'text': 'Only ranked submitted plays.'
        }
    )


def send_play_pp_ranking_webhook(
        api: Ossapi,
        latest_timestamp: datetime,
        mode: str,
        country: str,
        test: bool,
        top: int = 5
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
    scores: list[Score] = []
    for score_id, score_data in list(mapped_scores.items())[:top]:
        # TODO: this could be wrapped in a function to have checking if the score
        #       is correct
        if score_data['score_type'] == 'old':
            score = api.score_mode(mode, score_id)
        else:
            score = api.score(score_id)

        scores.append(score)

    # end early if no scores are to be found
    if len(scores) == 0:
        logger.warning('No scores to be listed. :(')
        return

    # make the list of the top 10 as a separate webhook
    pp_list_embed = create_pp_record_list_embed(scores)
    send_webhook(
        username=f'top {top} pp records of the day',
        embeds=[pp_list_embed],
        avatar_url='https://iili.io/JmEwJhF.png',
    )

    # send the highest pp play
    top_pp_embed = create_embed_from_play(api, scores[0])
    send_webhook(
        username='pp record of the day',
        embeds=[top_pp_embed],
        avatar_url='https://iili.io/JmEwJhF.png',
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
        description='Send a Discord webhook message from fetched data, requires leaderboard_scrape.py to be ran first!')

    parser.add_argument('--mode', type=str, default='fruits',
                        help='Define what mode, uses the parameters used on osu site.')
    parser.add_argument('--country', type=str, default='PH',
                        help='What country to make a webhook message from. Uses 2 letter country codes.')
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
