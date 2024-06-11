from datetime import datetime
from scripts.json_player_data import MappedPlayerDataCollection, get_comparison_and_mapped_data

import argparse
import scripts.general_utils as util
import scripts.html_utils as html

def generate_html_from_data(
    data:MappedPlayerDataCollection, 
    data_difference:MappedPlayerDataCollection = None,
    timestamp:float = 0.0, 
    test:bool = False,
    output_file:str = 'docs/index.html',
) -> str:
    rows = ''
    
    pp_gain = (0, 'nobody')
    rank_gain = (0, 'nobody')
    pc_gain = (0, 'nobody')
    pp_total = 0
    pc_total = 0
    
    def td(td):
        return html.elem('td', td)
    
    def avatar(user_id) -> str:
        image = html.elem(tag_name='img', **{
            'src': f'https://a.ppy.sh/{user_id}',
            'loading': 'lazy'
        })
        return td(image)
    
    def difference_td(id, stat, return_change=False):
        nonlocal pp_gain, rank_gain, pc_gain, pp_total, pc_total
        
        if data_difference is None:
            return td(data[id].get(stat))
        
        _green = 'class="increase"'
        _red = 'class="decrease"'
        
        current = data[id].get(stat)
        compare = data_difference[id].get(stat, 0)
        
        if stat == 'pp':
            pp_total += compare
            if compare > pp_gain[0]:
                pp_gain = (compare, data[id]['ign'])
        
        if stat == 'country_rank':
            if compare > rank_gain[0]:
                rank_gain = (compare, data[id]['ign'])
        
        if stat == 'play_count':
            pc_total += compare
            if compare > pc_gain[0]:
                pc_gain = (compare, data[id]['ign'])
        
        if return_change:
            if compare > 0:
                return 'up'
            elif compare < 0:
                return 'down'
        
        if stat in ['acc', 'pp']:
            compare = round(compare, 2)
        
        sign = '+' if compare > 0 else ''
        style = _red if compare < 0 else _green
        change = f'<sup {style}>({sign}{compare})</sup>' if compare != 0 else ''
        
        if stat in ['acc']:
            return td(f'{current:.2f}%{change}')
        else:
            return td(f'{current:,}{change}')
    
    for user_id in data:
        tr_class = ''
        tr_class_list = []

        pic = avatar(user_id)
        rank = difference_td(user_id, 'country_rank')
        rankc = difference_td(user_id, 'country_rank', True)
        ign = td(data[user_id]['ign'])
        pp = difference_td(user_id, 'pp')
        acc = difference_td(user_id, 'acc')
        pc = difference_td(user_id, 'play_count')
        x = difference_td(user_id, 'rank_x')
        s = difference_td(user_id, 'rank_s')
        a = difference_td(user_id, 'rank_a')
        
        if data_difference[user_id]['new_entry']:
            tr_class_list.append('new-entry')
        
        if rankc == 'up':
            tr_class_list.append('rank-up')
        elif rankc == 'down':
            tr_class_list.append('rank-down')
        
        if len(tr_class_list) > 0:
            tr_class = ' '.join(tr_class_list)
            tr_class = f' class="{tr_class}"'

        rows += f'<tr{tr_class}>{rank}{pic}{ign}{pp}{acc}{pc}{x}{s}{a}</tr>\n'
    
    formatted_time = util.timestamp_utc_offset(
        timestamp=timestamp,
        time_offset=8,
        time_format="%Y-%m-%d %H:%M:%S"
    )

    replacements = {
        'updated_at': formatted_time,
        'pp_gain': '{:,}'.format(round(pp_gain[0])),
        'pp_name': pp_gain[1],
        'rank_gain': '{:,}'.format(rank_gain[0]),
        'rank_name': rank_gain[1],
        'pc_gain': '{:,}'.format(pc_gain[0]),
        'pc_name': pc_gain[1],
        'pp_total': round(pp_total,2),
        'pc_total': '{:,}'.format(pc_total),
        'rows': rows,
    }
    
    if test:
        output_file = 'tests/' + output_file
    
    output_file = html.create_page_from_template(
        template_path='docs/main-page.template.html',
        output_path=output_file,
        **replacements
    )
    
    return output_file

def generate_page_from_dates(
    base_date = datetime.now(),
    compare_date_offset = 1,
    output_file = 'docs/index.html',
    country = 'PH',
    mode = 'fruits',
    test = False,
) -> None:
    processed_data = get_comparison_and_mapped_data(base_date, compare_date_offset, country, mode, test)
    latest_mapped_data = processed_data.latest_mapped_data
    comparison_mapped_data = processed_data.comparison_mapped_data
    data_difference = processed_data.data_difference
    latest_data_timestamp = processed_data.latest_data_timestamp
    
    if latest_mapped_data is None:
        print('Cannot get latest data as of now.')
        return
    
    if comparison_mapped_data is None:
        print('Cannot get comparison data as of now.')
        return
    
    file_name = generate_html_from_data(
        data=latest_mapped_data, 
        data_difference=data_difference, 
        test=test, 
        timestamp=latest_data_timestamp,
        output_file = output_file,
    )
    
    print(file_name)

def main(country:str='PH', mode:str='fruits', option:str='yesterday', test:bool=False) -> None:
    options = {
        # (timedelta, file_name_output)
        # TODO: make the base dir only a single instance
        'yesterday': (1, 'docs/index.html'),
        'week': (7, 'docs/weekly.html'),
        'month': (30, 'docs/monthly.html'),
        'year': (365, 'docs/yearly.html'),

        # TODO: compare from start of month, year, etc..
    }

    day_offset, output_file = options.get(option, None)

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
    parser.add_argument('--range', type=str, default='yesterday', help='What would be the comparison date to be done.')
    parser.add_argument('--test', action='store_true', help='Just do tests')
    
    args = parser.parse_args()
    
    main(country=args.country, mode=args.mode, option=args.range, test=args.test)