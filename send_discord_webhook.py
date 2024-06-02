from ossapi import Ossapi, Score
from datetime import datetime
from dotenv import load_dotenv

from scripts.discord_webhook import (
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

def get_recent_top_play_of_user(api:Ossapi, user_id, limit=5) -> Score:
    data = api.user_scores(user_id, 'best', limit=limit)

    data.sort(key=lambda x: x.created_at, reverse=True)

    return data[0]

def create_embed_from_play(data:Score):
    osu_username = data._user.username
    osu_avatar = data._user.avatar_url
    score = data.statistics
    max_combo = data.max_combo
    rank = str(data.rank)
    mods = str(data.mods)
    score_time = data.created_at.strftime('%Y-%m-%dT%H:%m:%S.%fZ')

    embed_data = embed_maker(
        title=data.beatmapset.title + f' [{data.beatmap.version}]',
        description=f'**{rank}** {score.count_300}/{score.count_100}/{score.count_50} {max_combo}x +{mods}',
        fields=[
            {
                "name": "Accuracy",
                "value": str(data.accuracy * 100),
                "inline": True,
            },
            {
                "name": "PP",
                "value": str(data.pp),
                "inline": True,
            }
        ],
        url=str(data.beatmap.url),
        thumbnail={
            "url": data.beatmapset.covers.list
        },
        author={
            "name": osu_username,
            "icon_url": osu_avatar
        },
        timestamp=score_time,
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
    
    active_players = get_sorted_dict_on_stat(data_difference, 'play_count', True)
    pp_gainers = get_sorted_dict_on_stat(data_difference, 'pp', True)
    rank_gainers = get_sorted_dict_on_stat(data_difference, 'rank', True)
    
    def _total_stat(data, key):
        return sum([data[i][key] for i in data if data[i][key] > 0])
    
    total_pc = _total_stat(active_players, 'play_count')
    total_pp = _total_stat(pp_gainers, 'pp')
    total_rank = _total_stat(rank_gainers, 'rank')
    
    pp_field, rank_field, pc_field = generate_player_summary_fields(
        pp_gainers, rank_gainers, active_players,
        latest_mapped_data, 
        comparison_mapped_data
    )
    
    footer = {
        'text': 'Updates delivered daily at around midnight. Inaccurate data? Blame Eoneru.',
    }
    
    send_webhook(
        content='``` ```',
        embeds=[
            embed_maker(
                title='Top 5 activity rankings for {}'.format(latest_date.strftime('%B %d, %Y')),
                description='There are: **{}** players who farmed, **{}** players who climbed the PH ranks, and **{}** players who played the game.\n\nIn __total__ there were: **{}pp**, **{} ranks**, and **{} play count** gained this day!'.format(
                    len(pp_gainers.items()),
                    len([i for i in rank_gainers.items() if i[1]['rank'] > 0]),
                    len(active_players.items()),
                    total_pp,
                    total_rank,
                    total_pc,
                ),
                fields=[
                    pp_field,
                    rank_field,
                    pc_field,
                ],
                footer=footer,
                color=12517310
            ),
        ],
        username='Top 1k osu!catch PH tracker',
        avatar_url='https://iili.io/JQmQKKl.png'
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