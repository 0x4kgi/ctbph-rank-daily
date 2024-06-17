from datetime import datetime
from dotenv import load_dotenv
from ossapi import Ossapi, GameMode, RankingType, Score, models
import json, time, argparse, re, os

from scripts.json_player_data import (
    MappedPlayerData,
    MappedScoreData,
    RawPlayerDataCollection,
    get_comparison_and_mapped_data,
    get_sorted_dict_on_stat,
)
from send_discord_webhook import get_recent_plays_of_user

def encode_to_map(map: list[str], data: dict[str, str], key: str) -> tuple[str, list[any]]:
    return data[key], [data[index] for index in map]

def format_data_from_rows(rows:models.Rankings) -> list[MappedPlayerData]:
    rows_data: list[MappedPlayerData] = []
    
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

def get_page_rankings(
    page: int = 1,
    mode: str = GameMode.CATCH,
    country: str = None,
) -> list[MappedPlayerData]:
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')

    api = Ossapi(client_id, client_secret)
    data = api.ranking(mode, RankingType.PERFORMANCE, country=country, cursor={'page':page})

    page_data = format_data_from_rows(data)

    return page_data

def get_rankings(
    mode: str = 'osu',
    country: str = None,
    pages: str = 1
) -> RawPlayerDataCollection:
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

    full_data:RawPlayerDataCollection = {
        # INFO: increment by one every time you change the format of the
        #       resulting json file and change data/file_versions.json too
        'file_version': 1.01,
        'update_date': time.time(),
        'mode': mode,
        'country': country if country else 'all',
        'pages': pages,
        'map': value_mapping,
        'key': values_key,
        'data': {},
    }

    for page in range(int(pages)):
        fetch_start_time = time.time()

        page_data = get_page_rankings(page+1, mode, country)
        
        for data in page_data:
            uid, values = encode_to_map(value_mapping, data, values_key)
            full_data['data'][uid] = values
        
        fetch_duration = time.time() - fetch_start_time
        print(f'c: {country} m: {mode} c/f: {page+1}/{pages} OK: {fetch_duration:.4f}s')

    return full_data

def dump_to_file(
    data: RawPlayerDataCollection,
    test: bool = False,
    formatted: bool = False,
) -> str:
    mode = data.get('mode', None)
    country = data.get('country', None)

    if mode is None or country is None:
        print('!! Warning: mode or country is none...')

    file_type = data.get('type', None)
    
    today = datetime.now()
    date_string = today.strftime('%Y/%m/%d')

    output = json.dumps(data, separators=(',', ':'), indent=0 if formatted else None)
    
    if formatted:
        output2 = re.sub(r'(\d"):\[\s+' , r'\1:[' , output)
        output3 = re.sub(r'("|\w),\s+'  , r'\1,'  , output2)
        output =  re.sub(r'(\d)\s+\]'   , r'\1]'  , output3)
    
    if file_type:
        output_file = f'data/{date_string}/{country}-{mode}-{file_type}.json'
    else:
        output_file = f'data/{date_string}/{country}-{mode}.json'
    
    if test:
        output_file = 'tests/' + output_file
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as json_file:
        json_file.write(output)
    
    return output_file

def format_score_data_from_list(scores: list[Score]) -> list[MappedScoreData]:
    if len(scores) == 0:
        return []

    score_list = []

    _mode = {
        0: 'osu', 1: 'taiko', 2: 'fruits', 3: 'mania'
    }

    for score in scores:
        score_list.append({
            'score_id': score.id,
            'score_type': 'old' if len(str(score.id)) < 10 else 'new',
            #'score_mode': _mode[score.mode_int], # since the mode is in the json
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
    
    return score_list

def get_pp_plays(
    mode: str = 'fruits',
    country: str = 'PH',
    test: bool = False,
) -> RawPlayerDataCollection:
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')
    api = Ossapi(client_id, client_secret)

    # temporarily using the function, until i placed this on a module
    def sort_scores_by_pp(
        scores: list[Score],
        top: int =10,
        min_date: float = 0,
        max_date: float = datetime.now().timestamp(),
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

    processed_data = get_comparison_and_mapped_data(
        base_date=datetime.now(),
        compare_date_offset=1,
        country=country,
        mode=mode,
        test=test
    )

    if processed_data.latest_mapped_data is None:
        print('No latest data for comparison')
        return None
    if processed_data.comparison_mapped_data is None:
        print('No old data for comparison')
        return None
    
    active_players = get_sorted_dict_on_stat(
        data=processed_data.data_difference,
        stat='play_count',
        highest_first=True,
    )

    scores:list[Score] = []
    
    for user_id in active_players:
        print('Fetching scores for', active_players[user_id]['ign'], '...')
        # temporarily using the function, until i placed this on a module
        user_scores = get_recent_plays_of_user(
            api=api,
            user_id=user_id,
            type='recent',
            limit=active_players[user_id]['play_count'],
        )
        scores += user_scores
    
    scores = sort_scores_by_pp(scores, top=100)
    formatted_list = format_score_data_from_list(scores)

    value_mapping = [
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
    values_key = 'score_id'

    full_data = {
        'file_version': 1.011,
        'update_date': time.time(),
        'type': 'pp-records',
        'mode': mode,
        'country': country if country else 'all',
        'map': value_mapping,
        'key': values_key,
        'data': {},
    }

    for scr in formatted_list:
        id, values = encode_to_map(value_mapping, scr, values_key)
        full_data['data'][id] = values
    
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
    if not skip_rankings:
        # Gather player rankings
        data = get_rankings(mode=mode, country=country, pages=pages)
        output_file = dump_to_file(data=data, test=test, formatted=formatted)
        print(output_file)
    else:
        print('Skipping gathering of rankings')

    if not skip_pp_plays:
        # Get active players, based on playcount
        pp_data = get_pp_plays(mode=mode, country=country, test=test)

        if pp_data is None:
            print('Incomplete data for pp listing, skipping gathering of pp plays')
            return

        output_file = dump_to_file(data=pp_data, test=test, formatted=formatted)
        print(output_file)
    else:
        print('Skipping gathering of pp plays')

if __name__ == '__main__':
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Gets the leaderboard for a mode and country. Via web scraping')
    
    parser.add_argument('-m', '--mode', type=str, default='2', help="What game mode to scan for. You can use owo bot's -m params or short hands like ctb, std, etc.")
    parser.add_argument('-p', '--pages', type=int, default=20, help='Number of pages to scan, maximum of 200. Defaults to 1')
    parser.add_argument('-c', '--country', type=str, default='PH', help="What country's leaderboard to scan for. Uses the 2 letter system (US, JP, PH, etc.)")
    parser.add_argument('--test', action='store_true', help='Just do tests')
    parser.add_argument('--formatted', action='store_true', help='Make the output .json to be somewhat readable')
    parser.add_argument('--skip-pp-plays', action='store_true', help='Do not try to gather top pp plays.')
    parser.add_argument('--skip-rankings', action='store_true', help='Skip gathering leaderboard rankings.')

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
        exit()
    
    run(
        mode=mode,
        country=args.country,
        pages=args.pages,
        formatted=args.formatted,
        test=args.test,
        skip_pp_plays=args.skip_pp_plays,
        skip_rankings=args.skip_rankings,
    )