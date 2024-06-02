import json, os

def sort_data_dictionary(
    data:dict[str,dict],
    key:str,
    reversed:bool=False
) -> dict[str, dict[str, str|int|float]]:
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
    data:dict[str,dict],
    stat:str,
    highest_first:bool=False
) -> dict[str, dict[str, str|int|float]]:
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


def get_data_at_date(date:str,country:str,mode:str,test:bool=False):
    current_dir = os.path.dirname(__file__)
    
    try:
        target_file = f'data/{date}/{country}-{mode}.json'
        
        if test:
            target_file = 'tests/' + target_file

        file_path = os.path.join(current_dir, '../' + target_file)

        with open(file_path) as file:
            data = json.load(file)
    except OSError as osx:
        return None
        
    return data

def compare_player_data(today_data:dict[str,str], yesterday_data:dict[str,str]):
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
            
            if stat == 'rank':
                difference = 0 - difference
            
            data[t][stat] = difference

    return data

def map_player_data(data:dict[str,any]) -> dict[str,dict[str,str]]:
    decoded_data = {}
    
    map = data['map']
    player_data = data['data']
    
    for player in player_data:
        decoded_data[player] = {
            map[i]: player_data[player][i] for i in range(len(map))
        }
    
    return decoded_data