from ossapi import Ossapi, Score
from data_to_html import get_data_at_date, compare_player_data, map_player_data
from datetime import datetime, timedelta
from dotenv import load_dotenv
import argparse, os, requests, math

def embed_maker(
    title:str=None,
    description:str=None,
    url:str=None,
    color:str=None,
    fields:list[dict[str,str]]=None,
    author:dict[str,str]=None,
    footer:dict[str,str]=None,
    timestamp:str=None,
    image:dict[str,str]=None,
    thumbnail:dict[str,str]=None,
):
    return {
        key: value for key, value in locals().items() if value is not None
    }

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

def send_embed(content:str=':)', embeds:list=[]):
    webhook_url = os.getenv('WEBHOOK_URL')

    payload = {
        "embeds": embeds,
        "content": content,
    }

    response = requests.post(
        webhook_url,
        json=payload
    )

    if response.status_code == 204:
        print('Embed sent successfully!')
    else:
        print(f'Failed to send embed. Status code: {response.status_code}')

def sort_data_dictionary(data:dict, key:str, reversed:bool=False) -> dict:
    return dict(
        # what the fuck is this, python
        sorted(data.items(), key=lambda x: x[1][key], reverse=reversed)
    )

def get_sorted_list_on_stat(data:dict, stat:str, highest_first:bool=False) -> dict:
    # this is so goofy as fuck
    return {
        i: data[i]
            for i in sort_data_dictionary(data, stat, highest_first)
                if data[i][stat] != 0
    }

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
    comparison_date = latest_date - timedelta(days=1)
    
    # this should be in a function, since i feel like im going to repeat this a lot
    # TODO: simplify this and do the above comment, thanks
    latest_data = get_data_at_date(
        latest_date.strftime('%Y/%m/%d'),
        country=country,
        mode=mode,
        test=test,
    )
    
    comparison_data = get_data_at_date(
        comparison_date.strftime('%Y/%m/%d'),
        country=country,
        mode=mode,
        test=test,
    )
    
    data_difference = compare_player_data(
        map_player_data(latest_data),
        map_player_data(comparison_data)
    )
    
    active_players = get_sorted_list_on_stat(data_difference, 'play_count', True)
    pp_gainers = get_sorted_list_on_stat(data_difference, 'pp', True)
    rank_gainers = get_sorted_list_on_stat(data_difference, 'rank', True)
    
    def _total_stat(data, key):
        return sum([data[i][key] for i in data if data[i][key] > 0])
    
    total_pc = _total_stat(active_players, 'play_count')
    total_pp = _total_stat(pp_gainers, 'pp')
    total_rank = _total_stat(rank_gainers, 'rank')
    
    pp_field, rank_field, pc_field = generate_player_summary_fields(
        pp_gainers, rank_gainers, active_players,
        map_player_data(latest_data), 
        map_player_data(comparison_data)
    )
    
    footer = {
        'text': 'Inaccurate? Blame @Eoneru.',
    }
    
    send_embed(None, [
        embed_maker(
            title='Top 5 activity rankings for <t:{}:D>'.format(int(latest_date.timestamp())),
            description='There are: **{}** players who farmed, **{}** players who climbed the PH ranks, and **{}** players who played the game.\n\nIn __total__ there were: **{}pp**, **{} ranks**, and **{} play count** gained today! (or yesterday? idk)'.format(
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
    ])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate page from fetched data, requires leaderboard_scrape.py to be ran first!')
    
    parser.add_argument('--mode', type=str, default='fruits', help='Define what mode, uses the parameters used on osu site.')
    parser.add_argument('--country', type=str, default='PH', help='What country to make a page from. Uses 2 letter country codes.')
    parser.add_argument('--test', action='store_true', help='Just do tests')
    
    args = parser.parse_args()
    
    load_dotenv()
    
    main(
        country=args.country,
        mode=args.mode,
        test=args.test,
    )