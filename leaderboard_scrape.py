from datetime import datetime
from typing import Any
from dotenv import load_dotenv
from ossapi import Ossapi, GameMode, RankingType, models
import json, time, argparse, re, os

from scripts.json_player_data import MappedPlayerData, MappedPlayerDataCollection, RawPlayerDataCollection

def extract_data_from_rows(rows:models.Rankings) -> list[MappedPlayerData]:
    rows_data:list[MappedPlayerData] = []
    
    for data in rows.ranking:
        rows_data.append({
            'country_rank': data.country_rank,
            'global_rank' : data.global_rank,
            'id'          : data.user.id,
            'ign'         : data.user.username,
            'pp'          : int(round(data.pp)),
            'acc'         : data.hit_accuracy,
            'play_count'  : data.play_count,
            'rank_x'      : data.grade_counts.ss + data.grade_counts.ssh,
            'rank_s'      : data.grade_counts.s + data.grade_counts.sh,
            'rank_a'      : data.grade_counts.a,
            'play_time'   : data.play_time,
            'total_score' : data.total_score,
            'ranked_score': data.ranked_score,
            'total_hits'  : data.total_hits,
        })

    return rows_data

def get_page_rankings(page:int=1, mode:str=GameMode.OSU, country:str=None) -> list[MappedPlayerData]:
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')

    api = Ossapi(client_id, client_secret)
    data = api.ranking(mode, RankingType.PERFORMANCE, country=country, cursor={'page':page})

    page_data = extract_data_from_rows(data)

    return page_data

def get_rankings(mode:str='osu', country:str=None, pages:str=1) -> RawPlayerDataCollection:
    pages = min(pages, 200)

    value_mapping = [
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
    values_key = 'id'

    def _encode_to_map(map: list[str], data: dict[str, str], key: str) -> tuple[str, list[Any]]:
        return data[key], [data[index] for index in map]

    full_data:RawPlayerDataCollection = {
        # INFO: increment by one every time you change the format of the
        #       resulting json file and change data/file_versions.json too
        'file_version': 1,
        'update_date': time.time(),
        'mode': mode,
        'country': country if country else 'all',
        'pages': pages,
        'map': value_mapping,
        'data': {},
    }

    for page in range(int(pages)):
        fetch_start_time = time.time()

        page_data = get_page_rankings(page+1, mode, country)
        
        for data in page_data:
            uid, values = _encode_to_map(value_mapping, data, values_key)
            full_data['data'][uid] = values
        
        fetch_duration = time.time() - fetch_start_time
        print(f'c: {country} m: {mode} c/f: {page+1}/{pages} OK: {fetch_duration:.4f}s')

    return full_data

def dump_to_file(data:RawPlayerDataCollection, test:bool=False, formatted:bool=False) -> str:
    mode = data['mode']
    country = data['country']
    pages = data['pages']
    
    today = datetime.now()
    date_string = today.strftime('%Y/%m/%d')

    output = json.dumps(data, separators=(',', ':'), indent=0 if formatted else None)
    
    if formatted:
        output2 = re.sub(r'(\d"):\[\s+' , r'\1:[' , output)
        output3 = re.sub(r'("|\w),\s+'  , r'\1,'  , output2)
        output =  re.sub(r'(\d)\s+\]'   , r'\1]'  , output3)
    
    output_file = f'data/{date_string}/{country}-{mode}.json'
    if test:
        output_file = 'tests/' + output_file
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as json_file:
        json_file.write(output)
    
    return output_file

def main() -> None:
    parser = argparse.ArgumentParser(description='Gets the leaderboard for a mode and country. Via web scraping')
    
    parser.add_argument('-m', '--mode', type=str, default='2', help="What game mode to scan for. You can use owo bot's -m params or short hands like ctb, std, etc.")
    parser.add_argument('-p', '--pages', type=int, default=20, help='Number of pages to scan, maximum of 200. Defaults to 1')
    parser.add_argument('-c', '--country', type=str, default='PH', help="What country's leaderboard to scan for. Uses the 2 letter system (US, JP, PH, etc.)")
    parser.add_argument('--test', action='store_true', help='Just do tests')
    parser.add_argument('--formatted', action='store_true', help='Make the output .json to be somewhat readable')
    
    args = parser.parse_args()
    
    mode_map = {
        '0': 'osu', 'osu': 'osu', 'std': 'osu', 'standard': 'osu', 's': 'osu',
        '1': 'taiko', 'taiko': 'taiko', 'taco': 'taiko', 't': 'taiko',
        '2': 'fruits', 'ctb': 'fruits', 'fruits': 'fruits', 'catch': 'fruits', 'c': 'fruits',
        '3': 'mania', 'mania': 'mania', 'm': 'mania'
    }
    mode = mode_map.get(args.mode)
    if mode is None:
        print(f'This mode: "{args.mode}" is not a valid one. Try again')
        return
    
    data = get_rankings(mode=mode, country=args.country, pages=args.pages)
    output_file = dump_to_file(data=data, test=args.test, formatted=args.formatted)
    
    print(output_file)

if __name__ == '__main__':
    load_dotenv()
    main()