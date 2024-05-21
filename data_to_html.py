from datetime import datetime, timedelta, timezone
import json, time, argparse, os

def map_player_data(data:dict[str,any]) -> dict[str,dict[str,str]]:
    decoded_data = {}
    
    map = data['map']
    player_data = data['data']
    
    for player in player_data:
        decoded_data[player] = {
            map[i]: player_data[player][i] for i in range(len(map))
        }
    
    return decoded_data

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

def get_data_at_date(date:str,country:str,mode:str):
    try:
        with open(f'data/{date}/{country}-{mode}.json') as file:
            data = json.load(file)
    except OSError as osx:
        return None
        
    return data

def generate_html_from_data(
    data:dict[str,dict], 
    data_difference:dict[str,dict] = None,
    timestamp:float = 0.0, 
    test:bool = False,
    output_file:str = 'index.html',
):
    with open('html/main-page.template.html') as file:
        html_template = file.read()
    
    rows = ''
    
    pp_gain = (0, '')
    rank_gain = (0, '')
    pc_gain = (0, '')
    
    def _td(td):
        return f'<td>{td}</td>'
    
    def _img(i):
        _s = 50
        _i = f'<img src="https://a.ppy.sh/{i}" loading="lazy" width={_s} height={_s}>'
        return _td(_i)
    
    def _comp(id, stat, return_change=False):
        nonlocal pp_gain, rank_gain, pc_gain
        
        if data_difference is None:
            return _td(data[id][stat])
        
        _green = 'class="increase"'
        _red = 'class="decrease"'
        
        current = data[id][stat]
        compare = data_difference[id][stat]
        
        if stat == 'pp':
            if compare > pp_gain[0]:
                pp_gain = (compare, data[id]['ign'])
        
        if stat == 'rank':
            if compare > rank_gain[0]:
                rank_gain = (compare, data[id]['ign'])
        
        if stat == 'play_count':
            if compare > pc_gain[0]:
                pc_gain = (compare, data[id]['ign'])
        
        if return_change:
            if compare > 0:
                return 'up'
            elif compare < 0:
                return 'down'
        
        if stat == 'acc':
            compare = round(compare, 3)
        
        sign = '+' if compare > 0 else ''
        style = _red if compare < 0 else _green
        change = f'<br><span {style}>({sign}{compare})</span>' if compare != 0 else ''
        
        if stat == 'acc':
            return _td(f'{current:.2f}{change}')
        else:
            return _td(f'{current}{change}')
    
    for l in data:
        tr_class = ['new-entry' if data_difference[l]['new_entry'] else '']
        
        pic = _img(l)
        rank = _comp(l, 'rank')
        rankc = _comp(l, 'rank', True)
        ign = _td(data[l]['ign'])
        pp = _comp(l, 'pp')
        acc = _comp(l, 'acc')
        pc = _comp(l, 'play_count')
        x = _comp(l, 'rank_x')
        s = _comp(l, 'rank_s')
        a = _comp(l, 'rank_a')
        
        if rankc == 'up':
            tr_class.append('rank-up')
        elif rankc == 'down':
            tr_class.append('rank-down')
        
        tr_class = ' '.join(tr_class)
        rows += f'<tr class="{tr_class}">{rank}{pic}{ign}{pp}{acc}{pc}{x}{s}{a}</tr>\n'
    
    dt_object = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    formatted_time = dt_object.strftime("%Y-%m-%d %H:%M:%S")
    
    output = html_template.replace('{{__rows__}}', rows)
    output = output.replace('{{__updated_at__}}', formatted_time)
    
    output = output.replace('{{__pp_gain__}}', str(pp_gain[0]))
    output = output.replace('{{__pp_name__}}', pp_gain[1])
    
    output = output.replace('{{__rank_gain__}}', str(rank_gain[0]))
    output = output.replace('{{__rank_name__}}', rank_gain[1])
    
    output = output.replace('{{__pc_gain__}}', str(pc_gain[0]))
    output = output.replace('{{__pc_name__}}', pc_gain[1])
    
    if test:
        output_file = 'tests/' + output_file
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_output_path = os.path.join(script_dir, output_file)
    os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
    with open(output_file, 'w') as file:
        file.write(output)
    
    return output_file

def generate_page_from_dates(
    base_date = datetime.now(),
    compare_date_offset = 1,
    output_file = 'index.html',
    country = 'PH',
    mode = 'fruits',
    test = False,
):
    latest_date = base_date
    comparison_date = latest_date - timedelta(days=compare_date_offset)

    latest_string = latest_date.strftime('%Y/%m/%d')
    comparison_string = comparison_date.strftime('%Y/%m/%d')

    latest_data = get_data_at_date(latest_string, country, mode)

    if latest_data is None:
        print(f'Data for {latest_string} {country} {mode} does not exist yet. Ending early.')
        return

    latest_mapped_data = map_player_data(latest_data)

    data_difference = None

    comparison_data = get_data_at_date(comparison_string, country, mode)
    comparison_mapped_data = None

    if comparison_data is not None:
        comparison_mapped_data = map_player_data(comparison_data)
        data_difference = compare_player_data(latest_mapped_data, comparison_mapped_data)
    else:
        print(f'Data for {comparison_string} does not exist yet. Creating nothing. Skipping generating {output_file}')
        return
    
    file_name = generate_html_from_data(
        data=latest_mapped_data, 
        data_difference=data_difference, 
        test=test, 
        timestamp=latest_data['update_date'],
        output_file = output_file,
    )
    
    print(file_name)

def main(country:str='PH', mode:str='fruits', option:str='yesterday', test:bool=False) -> None:
    options = {
        # (timedelta, file_name_output)
        'yesterday': (1, 'index.html'),
        'week': (7, 'weekly.html'),
        'month': (30, 'monthly.html'),
        'year': (365, 'yearly.html'),

        # TODO: compare from start of month, year, etc..
    }

    day_offset, output_file = options.get(option)

    if day_offset is None:
        print('Pick a valid option. [yesterday, week, monthly]')
        return

    generate_page_from_dates(
        base_date=datetime.now(),
        compare_date_offset=day_offset,
        country=country, mode=mode, test=test,
        output_file=output_file
    )

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate page from fetched data, requires leaderboard_scrape.py to be ran first!')
    
    parser.add_argument('--mode', type=str, default='fruits', help='Define what mode, uses the parameters used on osu site.')
    parser.add_argument('--country', type=str, default='PH', help='What country to make a page from. Uses 2 letter country codes.')
    parser.add_argument('--test', action='store_true', help='Just do tests')
    
    args = parser.parse_args()
    
    main(country=args.country, mode=args.mode, test=args.test)