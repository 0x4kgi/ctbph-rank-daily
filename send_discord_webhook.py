from ossapi import GameMode, Ossapi, Score, User
from datetime import datetime
from dotenv import load_dotenv
from typing import TypedDict, NotRequired

from scripts.discord_webhook import (
    Embed,
    EmbedField,
    embed_maker,
    send_webhook,
)
from scripts.json_player_data import (
    get_comparison_and_mapped_data,
    get_sorted_dict_on_stat,
)

import argparse, os, math

def get_pp_pb_place_from_weight(weight:float) -> int:
    base = 0.95
    factor = 100
    ln_base = math.log(base)
    ln_target = math.log(weight / factor)
    n_minus_1 = ln_target / ln_base
    n = n_minus_1 + 1
    return round(n)

def get_recent_plays_of_user(api:Ossapi, user_id, type:str='best', limit=5) -> list[Score]:
    print('recent plays: ', user_id, type, limit)
    data = api.user_scores(
        user_id,
        type,
        limit=limit,
        mode=GameMode.CATCH,
        include_fails=False
    )
    print('# of plays: ', len(data))
    return data

def get_user_info(api:Ossapi, user_id) -> User:
    return api.user(user_id, mode=GameMode.CATCH)

def simplify_number(num):
    """
    ChatGPT code, i got too lazy.
    
    Simplifies a number by adding appropriate suffixes (k, M, B, T) for thousands, millions, billions, and trillions.
    
    Parameters:
    num (int or float): The number to simplify.
    
    Returns:
    str: The simplified number with the appropriate suffix.
    """
    suffixes = ['', 'k', 'M', 'B', 'T']
    magnitude = 0
    
    # Determine the magnitude
    while abs(num) >= 1000 and magnitude < len(suffixes) - 1:
        magnitude += 1
        num /= 1000.0
    
    # Format the number with the appropriate suffix
    if magnitude == 0:
        return f"{num:.0f}"
    else:
        return f"{num:.2f}{suffixes[magnitude]}"

def get_emote_for_score_grade(grade:str) -> str:
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

def create_embed_from_play(api:Ossapi, data:Score) -> Embed:
    user = get_user_info(api, data.user_id)
    
    osu_username = user.username
    osu_avatar = user.avatar_url
    osu_url = f'https://osu.ppy.sh/users/{user.id}'
    user_pp = round(user.statistics.pp,0)
    ph_rank = user.statistics.country_rank

    score = data.statistics
    max_combo = data.max_combo
    rank = get_emote_for_score_grade(data.rank)
    mods = str(data.mods)
    score_time = data.created_at.strftime('%Y-%m-%dT%H:%m:%S.%fZ')
    
    embed_data = embed_maker(
        title=data.beatmapset.title + f' [{data.beatmap.version}] [{data.beatmap.difficulty_rating:,.2f}*]',
        description=f'**{rank}** • {score.count_300}/{score.count_100}/{score.count_50}/{score.count_miss} • {max_combo}x',
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

    return [ pp_field, rank_field, pc_field, rs_field ]

def description_maker(
    active_players:dict,
    pp_gainers:dict,
    rank_gainers:dict,
    ranked_score_gainers:dict,
) -> str:
    import re
    
    def above_zero_count(data:dict, key:str) -> int:
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
    description = """There are: **{:,}** players who farmed,
    **{:,}** players who climbed the PH ranks,
    and **{:,}** players who played the game.!n!n
    In __total__ there were: **{:,}pp**,
    **{:,} ranks**,
    **{:,} play count**,
    and **{} ranked score** gained this day!""".format(
        pp_gain_count,
        rank_gain_count,
        active_count,
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

def send_activity_ranking_webhook(
    latest_mapped_data:dict,
    comparison_mapped_data:dict,
    data_difference:dict,
    latest_date:datetime=datetime.now(),
) -> None:
    
    # TODO: this is getting ridiculous, find a way to simplify this
    active_players = get_sorted_dict_on_stat(data_difference, 'play_count', True)
    pp_gainers = get_sorted_dict_on_stat(data_difference, 'pp', True)
    rank_gainers = get_sorted_dict_on_stat(data_difference, 'country_rank', True)
    ranked_score_gainers = get_sorted_dict_on_stat(data_difference, 'ranked_score', True)
    
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
    
    main_embed = embed_maker(
        title='Top 5 activity rankings for {}'.format(latest_date.strftime('%B %d, %Y')),
        url='https://0x4kgi.github.io/ctbph-rank-daily/',
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
    
    send_webhook(
        content='``` ```',
        embeds=[ main_embed ],
        username='Top 1k osu!catch PH tracker',
        avatar_url='https://iili.io/JQmQKKl.png'
    )

def create_pp_record_list_embed(api:Ossapi, scores:list[Score]) -> Embed:
    def formatter(index:int, score:Score) -> str:
        def miss_format(miss) -> str:
            if miss:
                return f'{miss:,}❌'
            else:
                return '**Full Combo**'

        # 1. {pp}pp - Player
        info = '{}. **{:,.2f}**pp • **{}**\n'.format(
            index + 1,
            score.pp,
            score._user.username,
        )

        # map name and link also mod?
        info += ' - [**{} [{}]** [{:,.2f}*]]({}) +{}\n'.format(
            score.beatmapset.title,
            score.beatmap.version,
            score.beatmap.difficulty_rating,
            score.beatmap.url,
            score.mods,
        )

        # score statistics
        info += ' - {} / {:,.2f}% / {} / {:,}x\n'.format(
            get_emote_for_score_grade(score.rank),
            score.accuracy * 100,
            miss_format(score.statistics.count_miss),
            score.max_combo,
        )

        return info

    description:str = ''

    for index, scr in enumerate(scores):
        description += formatter(index, scr)
    
    return embed_maker(
        description=description,
        color=12891853,
        footer={
            'text': 'Only ranked submitted plays.'
        }
    )

def send_play_pp_ranking_webhook(api:Ossapi, data_difference:dict, latest_timestamp, comparison_timestamp):
    def sort_scores_by_pp(
        scores:list[Score],
        top=10,
        min_date:datetime=comparison_timestamp,
        max_date:datetime=latest_timestamp,
    ) -> list[Score]:
        
        def score_filter(score:Score) -> bool:
            timestamp = score.created_at.timestamp()
            if score.pp is None:
                return False
            if timestamp < min_date:
                return False
            if timestamp > max_date:
                return False
            return True
        
        filtered_scores:list[Score] = filter(score_filter, scores)
        
        return sorted(
            filtered_scores,
            key=lambda s: s.pp,
            reverse=True
        )[:top]
    
    active_players = get_sorted_dict_on_stat(
        data=data_difference,
        stat='play_count',
        highest_first=True
    )
    
    scores:list[Score] = []
    
    for user_id in active_players:
        print('Fetching scores for', active_players[user_id]['ign'], '...')
        user_scores = get_recent_plays_of_user(
            api=api,
            user_id=user_id,
            type='recent',
            limit=active_players[user_id]['play_count'],
        )
        scores += user_scores
    
    top = 5
    
    scores = sort_scores_by_pp(scores, top)

    # make the list of the top 10 as a separate webhook
    pp_list_embed = create_pp_record_list_embed(api, scores)
    send_webhook(
        username=f'top {top} pp records of the day',
        embeds=[ pp_list_embed ],
        avatar_url='https://iili.io/JmEwJhF.png',
    )
    
    # send the highest pp play
    top_pp_embed = create_embed_from_play(api, scores[0])
    send_webhook(
        username='pp record of the day',
        embeds=[ top_pp_embed ],
        avatar_url='https://iili.io/JmEwJhF.png',
    )

def main(country:str='PH', mode:str='fruits', test:bool=False):
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')
    api = Ossapi(client_id, client_secret)

    latest_date = datetime.now()
    processed_data = get_comparison_and_mapped_data(
        latest_date, 1, country, mode, test
    )
    latest_mapped_data = processed_data.latest_mapped_data
    comparison_mapped_data = processed_data.comparison_mapped_data
    data_difference = processed_data.data_difference
    latest_timestamp = processed_data.latest_data_timestamp
    comparison_timestamp = processed_data.comparison_data_timestamp
    
    if latest_mapped_data is None:
        print('Cannot get latest data as of now.')
        return
    
    if comparison_mapped_data is None:
        print('Cannot get comparison data as of now.')
        return
    
    send_activity_ranking_webhook(
        latest_mapped_data,
        comparison_mapped_data,
        data_difference,
        latest_date,
    )
    
    send_play_pp_ranking_webhook(
        api,
        data_difference,
        latest_timestamp,
        comparison_timestamp
    )

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Send a Discord webhook message from fetched data, requires leaderboard_scrape.py to be ran first!')
    
    parser.add_argument('--mode', type=str, default='fruits', help='Define what mode, uses the parameters used on osu site.')
    parser.add_argument('--country', type=str, default='PH', help='What country to make a webhook message from. Uses 2 letter country codes.')
    parser.add_argument('--test', action='store_true', help='Just do tests')
    
    args = parser.parse_args()
    
    load_dotenv()
    
    main(
        country=args.country,
        mode=args.mode,
        test=args.test,
    )