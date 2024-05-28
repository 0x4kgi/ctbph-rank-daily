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
    
    active_fields = [
        {
            'name': active_players[i]['ign'],
            'value': str(active_players[i]['play_count']) + ' play count',
        } for i in active_players
    ]
    
    pp_fields = [
        {
            'name': pp_gainers[i]['ign'],
            'value': str(pp_gainers[i]['pp']) + 'pp',
        } for i in pp_gainers
    ]
    
    rank_fields = [
        {
            'name': rank_gainers[i]['ign'],
            'value': str(rank_gainers[i]['rank']) + 'pp',
        } for i in rank_gainers if rank_gainers[i]['rank'] > 0
    ]
    
    send_embed('active and pp gainers', [
        embed_maker(title='rank gains', fields=rank_fields[:10]),
        embed_maker(title='play count uwu',fields=active_fields[:10]),
        embed_maker(title='top pp gainers for today',fields=pp_fields[:10]),
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