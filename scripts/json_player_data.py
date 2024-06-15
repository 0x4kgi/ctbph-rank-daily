from collections import namedtuple
from datetime import datetime, timedelta
from typing import Optional, TypedDict
import json, os

class MappedPlayerData(TypedDict):
    """Object for player data
    ```
    county_rank: int
    global_rank: int
    ign: str
    pp: float
    acc: float
    play_count: int
    rank_x: int
    rank_s: int
    rank_a: int
    play_time: int
    total_score: int
    ranked_score: int
    total_hits: int
    ```
    """
    county_rank: int
    global_rank: int
    ign: str
    pp: float
    acc: float
    play_count: int
    rank_x: int
    rank_s: int
    rank_a: int
    play_time: int
    total_score: int
    ranked_score: int
    total_hits: int

class MappedScoreData(TypedDict):
    """Object for score data
    ```
    score_type: str
    score_mods: str
    score_pp: float
    score_grade: str
    user_id: int
    user_name: str
    beatmapset_title: str
    beatmap_version: str
    beatmap_id: int
    beatmapset_id: int
    beatmap_difficulty: float
    full_combo: bool
    max_combo: int
    count_300: int
    count_100: int
    count_50: int
    count_miss: int
    accuracy: float
    ```
    """
    score_type: str
    score_mods: str
    score_pp: float
    score_grade: str
    
    user_id: int
    user_name: str
    
    beatmapset_title: str
    beatmap_version: str
    beatmap_id: int
    beatmapset_id: int
    beatmap_difficulty: float
    
    full_combo: bool
    max_combo: int
    count_300: int
    count_100: int
    count_50: int
    count_miss: int
    accuracy: float

class MappedPlayerDataCollection(TypedDict):
    """A collection of player data that includes the player id
    
    Mapped as follows:
    ```
    {
        user_id1: MappedPlayerData,
        user_id2: MappedPlayerData,
        user_id3: MappedPlayerData,
        ...
    }
    ```
    
    Using `.get()` should return `MappedPlayerData`
    """
    __getitem__: MappedPlayerData

class MappedScoreDataCollection(TypedDict):
    __getitem__: MappedScoreData
class RawPlayerDataCollection(TypedDict):
    """Object type when getting the contents of the json data file
    ```
    file_version: Optional[int]
    update_date: float
    mode: str
    country: str
    pages: int
    map: list[str]
    data: dict[str, list[int | str | float]]
    ```
    """
    file_version: Optional[float]
    update_date: float
    file_type: Optional[str]
    mode: str
    country: str
    pages: Optional[int]
    map: list[str]
    data: dict[str, list[int | str | float]]

def sort_data_dictionary(
    data:MappedPlayerDataCollection,
    key:str,
    reversed:bool=False
) -> MappedPlayerDataCollection:
    """Sorts mapped player data. 

    Args:
        data (dict[str,dict]): The mapped player data
        key (str): The field to sort from
        reversed (bool, optional): Can be interpreted as "highest first?". Defaults to False.

    Returns:
        dict: The mapped player data, now sorted to specified key.
    """
    return dict(
        sorted(data.items(), key=lambda x: x[1].get(key, 0), reverse=reversed)
    )

def get_sorted_dict_on_stat(
    data:MappedPlayerDataCollection,
    stat:str,
    highest_first:bool=False
) -> MappedPlayerDataCollection:
    """Sorts mapped player data and removes 0 values.

    Args:
        data (dict[str,dict]): Mapped player data.
        stat (str): The key to sort and filter out 0 values.
        highest_first (bool, optional): Highest value at the top?. Defaults to False.

    Returns:
        dict[str, dict[str, str|int|float]]: Sorted and filtered mapped player data
    """
    return {
        i: data[i]
        for i in sort_data_dictionary(data, stat, highest_first)
        if data[i].get(stat, 0) != 0
    }

def get_json(file_path: str, test: bool) -> dict:
    """Gets the json file at the specified path. Can be specified if grabbing from tests

    Args:
        file_path (str): File path
        test (bool): Is grabbing from the test folder?

    Returns:
        dict: The json data in dict
    """
    current_dir = os.path.dirname(__file__)
        
    if test:
        file_path = 'tests/' + file_path

    file_path = os.path.join(current_dir, '../' + file_path)
    
    print(f'Trying to get {file_path}...')
    
    try:
        with open(file_path) as file:
            data = json.load(file)
    except OSError as osx:
        print(f'{file_path} does not exist.')
        return None
        
    return data

def get_data_at_date(
    date:str,
    country:str,
    mode:str,
    file_type:str=None,
    test:bool=False
) -> RawPlayerDataCollection|None:
    """Gets the json data file for the date, country, mode specified

    Args:
        date (str): The date, in YYYY/MM/DD format
        country (str): Uses 2 letter country code
        mode (str): osu/taiko/fruits/mania
        test (bool, optional): Uses files in tests/ to avoid cluttering up main files. Defaults to False.

    Returns:
        dict: json as dictionary, `None` if the file does not exist yet
    """
    
    # TODO: maybe do something about this
    if file_type is not None:
        target_file = f'data/{date}/{country}-{mode}-{file_type}.json'
    else:
        target_file = f'data/{date}/{country}-{mode}.json'
    
    return get_json(file_path=target_file, test=test)

def compare_player_data(
    today_data:MappedPlayerDataCollection,
    yesterday_data:MappedPlayerDataCollection
) -> MappedPlayerDataCollection:
    data = {}
    
    for t in today_data:
        player = today_data.get(t)
        y_player = yesterday_data.get(t)
        data[t] = {
            'new_entry': False
        }
        
        if y_player is None:
            data[t]['new_entry'] = True
            # temporary band-aid fix
            for stat in player:
                if stat == 'ign':
                    data[t][stat] = player[stat]
                    continue
                data[t][stat] = 0
            continue
        
        for stat in player:
            if stat == 'ign':
                data[t][stat] = player[stat]
                continue
                
            t_stat = player.get(stat, 0)
            y_stat = y_player.get(stat, 0)
            difference = t_stat - y_stat
            
            if stat == 'country_rank':
                difference = 0 - difference
            
            data[t][stat] = difference

    return data

def map_player_data(data:RawPlayerDataCollection) -> MappedPlayerDataCollection|MappedScoreDataCollection:
    decoded_data:MappedPlayerDataCollection = {}
    
    map = data['map']
    player_data = data['data']
    
    for player in player_data:
        decoded_data[player] = {
            map[i]: player_data[player][i] 
            for i in range(len(map))
        }
    
    return decoded_data

ComparisonAndMappedData = namedtuple(
    typename='ComparisonAndMappedData',
    field_names=[
        'latest_mapped_data',
        'comparison_mapped_data',
        'data_difference',
        'latest_data_timestamp',
        'comparison_data_timestamp',
    ]
)

def get_comparison_and_mapped_data(
    base_date:datetime,
    compare_date_offset:int,
    country:str,
    mode:str,
    test:bool
) -> ComparisonAndMappedData:
    """Tries to compare the latest data from a specified date and older data 
    from the offset from the latest date and maps the data to become a valid
    json to be easily read on.

    Args:
        base_date (datetime): The datetime of the latest data to gather
        compare_date_offset (int): How many days old compared to the latest data
        country (str): 2 Letter country code
        mode (str): osu/taiko/fruits/mania
        test (bool): Use data from tests/

    Returns:
        tuple[0]: latest mapped data
        tuple[1]: comparison mapped data
        tuple[2]: data difference
        tuple[3]: latest data timestamp
        tuple[4]: comparison data timestamp
    """
    
    latest_date = base_date
    comparison_date = latest_date - timedelta(days=compare_date_offset)
    
    latest_data_timestamp = None
    comparison_data_timestamp = None

    latest_string = latest_date.strftime('%Y/%m/%d')
    comparison_string = comparison_date.strftime('%Y/%m/%d')

    latest_data = get_data_at_date(date=latest_string, country=country, mode=mode, test=test)
    latest_mapped_data = None

    if latest_data is not None:
        latest_data_timestamp = latest_data['update_date']
        latest_mapped_data = map_player_data(latest_data)

    data_difference = None

    comparison_data = get_data_at_date(date=comparison_string, country=country, mode=mode, test=test)
    comparison_mapped_data = None

    if comparison_data is not None and latest_data is not None:
        comparison_data_timestamp = comparison_data['update_date']
        comparison_mapped_data = map_player_data(comparison_data)
        data_difference = compare_player_data(latest_mapped_data, comparison_mapped_data)
    
    return ComparisonAndMappedData(
        latest_mapped_data=latest_mapped_data,
        comparison_mapped_data=comparison_mapped_data,
        data_difference=data_difference,
        latest_data_timestamp=latest_data_timestamp,
        comparison_data_timestamp=comparison_data_timestamp
    )