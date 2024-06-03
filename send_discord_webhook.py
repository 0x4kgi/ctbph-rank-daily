from ossapi import GameMode, Ossapi, Score, User
from datetime import datetime
from dotenv import load_dotenv

from scripts.discord_webhook import (
    Embed,
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
    data = api.user_scores(user_id, type, limit=limit, mode=GameMode.CATCH)

    return data

def get_user_info(api:Ossapi, user_id) -> User:
    return api.user(user_id, mode=GameMode.CATCH)

def create_embed_from_play(api:Ossapi, data:Score) -> Embed:
    user = get_user_info(api, data.user_id)
    
    osu_username = user.username
    osu_avatar = user.avatar_url
    osu_url = f'https://osu.ppy.sh/users/{user.id}'
    user_pp = round(user.statistics.pp,0)
    ph_rank = user.statistics.country_rank

    score = data.statistics
    max_combo = data.max_combo
    rank = str(data.rank).split('.')[-1]
    mods = str(data.mods)
    score_time = data.created_at.strftime('%Y-%m-%dT%H:%m:%S.%fZ')
    

    embed_data = embed_maker(
        title=data.beatmapset.title + f' [{data.beatmap.version}]',
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
        thumbnail={
            'url': data.beatmapset.covers.list
        },
        author={
            'name': f'{osu_username} • {user_pp:,}pp • PH{ph_rank}',
            'icon_url': osu_avatar,
            'url': osu_url,
        },
        timestamp=score_time,
        footer={
            'text': 'It would be a miracle if you see this embed.'
        }
    )

    return embed_data

def generate_player_summary_fields(pp_gainers, rank_gainers, active_players, latest_data, comparison_data):
    def format_field(name, data, formatter, stat, limit=5):
        return {
            'name': name,
            'value': '\n'.join(
                formatter(item) for item in list(data.items())[:limit] if item[1][stat] > 0
            )
        }
        
    def _uid_link(item):
        return item[0], f'https://osu.ppy.sh/users/{item[0]}'

    def _get_stats(uid, stat):
        nonlocal latest_data, comparison_data
        old = comparison_data[uid][stat]
        new = latest_data[uid][stat]
        return old, new
    
    def pp_formatter(item):
        uid, link = _uid_link(item)
        ign = item[1]['ign']
        gained = item[1]['pp']
        old, new = _get_stats(uid, 'pp')
        return f'1. [**{ign}**]({link}) • {old:,}pp → **{new:,}**pp (+**{gained:,}**pp)'

    def rank_formatter(item):
        uid, link = _uid_link(item)
        ign = item[1]['ign']
        gained = item[1]['rank']
        old, new = _get_stats(uid, 'rank')
        return f'1. [**{ign}**]({link}) • PH{old:,} → PH**{new:,}** (+**{gained:,}** ranks)'

    def pc_formatter(item):
        uid, link = _uid_link(item)
        ign = item[1]['ign']
        gained = item[1]['play_count']
        old, new = _get_stats(uid, 'play_count')
        return f'1. [**{ign}**]({link}) • {old:,} → {new:,} (+**{gained:,}** plays)'

    pp_field = format_field('farmers', pp_gainers, pp_formatter, 'pp')
    rank_field = format_field('PH rank climbers', rank_gainers, rank_formatter, 'rank')
    pc_field = format_field('"play more" gamers', active_players, pc_formatter, 'play_count')

    return pp_field, rank_field, pc_field

def description_maker(active_players:dict, pp_gainers:dict, rank_gainers:dict) -> str:
    import re
    
    def above_zero_count(data:dict, key:str) -> int:
        return len([i for i in data.items() if i[1][key] > 0])
    
    def total_stat(data, key):
        return sum([data[i][key] for i in data if data[i][key] > 0])
    
    active_count = above_zero_count(active_players, 'play_count')
    pp_gain_count = above_zero_count(pp_gainers, 'pp')
    rank_gain_count = above_zero_count(rank_gainers, 'rank')
    
    total_pc = total_stat(active_players, 'play_count')
    total_pp = total_stat(pp_gainers, 'pp')
    total_rank = total_stat(rank_gainers, 'rank')
    
    # use !n for newlines
    description = """There are: **{:,}** players who farmed,
    **{:,}** players who climbed the PH ranks,
    and **{:,}** players who played the game.!n!n
    In __total__ there were: **{:,}pp**,
    **{:,} ranks**,
    and **{:,} play count** gained this day!""".format(
        pp_gain_count,
        rank_gain_count,
        active_count,
        total_pp,
        total_rank,
        total_pc
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
    active_players = get_sorted_dict_on_stat(data_difference, 'play_count', True)
    pp_gainers = get_sorted_dict_on_stat(data_difference, 'pp', True)
    rank_gainers = get_sorted_dict_on_stat(data_difference, 'rank', True)
    
    pp_field, rank_field, pc_field = generate_player_summary_fields(
        pp_gainers, rank_gainers, active_players,
        latest_mapped_data, 
        comparison_mapped_data
    )
    
    footer = {
        'text': 'Updates delivered daily at around midnight. Inaccurate data? Blame Eoneru.',
    }
    
    main_embed = embed_maker(
        title='Top 5 activity rankings for {}'.format(latest_date.strftime('%B %d, %Y')),
        url='https://0x4kgi.github.io/ctbph-rank-daily/',
        description=description_maker(active_players, pp_gainers, rank_gainers),
        fields=[ pp_field, rank_field, pc_field ],
        footer=footer,
        color=12517310
    )
    
    send_webhook(
        content='``` ```',
        embeds=[ main_embed ],
        username='Top 1k osu!catch PH tracker',
        avatar_url='https://iili.io/JQmQKKl.png'
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
            if timestamp < min_date:
                return False
            if timestamp > max_date:
                return False
            return True
        
        filtered_scores:list[Score] = filter(score_filter, scores)
        
        return sorted(
            filtered_scores,
            key=lambda s: s.pp if s.pp is not None else 0.0,
            reverse=True
        )[:top]
    
    active_players = get_sorted_dict_on_stat(data_difference, 'play_count')
    
    scores:list[Score] = []
    
    for user_id in active_players:
        scores += get_recent_plays_of_user(
            api=api,
            user_id=user_id,
            type='recent',
            limit=active_players[user_id]['play_count']
        )
        print(f'uid: {user_id} OK')
    
    scores = sort_scores_by_pp(scores, 10)
    
    scr_embed = create_embed_from_play(api, scores[0])
    send_webhook(username='Top osu!catch PH pp play of the day', embeds=[scr_embed], avatar_url='https://iili.io/JmEwJhF.png')

def main(country:str='PH', mode:str='fruits', test:bool=False):
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')
    api = Ossapi(client_id, client_secret)

    latest_date = datetime.now()
    processed_data = get_comparison_and_mapped_data(
        latest_date, 1, country, mode, test
    )
    latest_mapped_data = processed_data[0]
    comparison_mapped_data = processed_data[1]
    data_difference = processed_data[2]
    latest_timestamp = processed_data[3]
    comparison_timestamp = processed_data[4]
    
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