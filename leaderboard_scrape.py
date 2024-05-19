from bs4 import BeautifulSoup
from datetime import datetime
import requests, json, time, argparse, re, os

def text(elem) -> str:
    return elem.get_text().strip()

def clean_int(value:str) -> int:
    return int(value.replace(',',''))

def clean_float(value:str) -> float:
    value = value.replace(',','')
    return(float(value.replace('%', '')))

def extract_user_data(elem) -> tuple[str,str]:
    # this could definitely change in the future
    # keeping [0] as of now
    user_a = elem.select('a.ranking-page-table__user-link-text.js-usercard')[0]
    user_id = user_a.get('data-user-id')
    user_name = text(user_a)
    return user_id, user_name

def extract_data_from_rows(rows) -> list[dict[str,str]]:
    INDEX = {
        'RANK' : 0,
        'IGN'  : 1,
        'ACC'  : 2,
        'PC'   : 3,
        'PP'   : 4,
        'X'    : 5,
        'S'    : 6,
        'A'    : 7,
    }
    
    def _get(source: list, index: str, mode='int'):
        _text = text(source[INDEX[index]]).replace('#','')
        if mode == 'int':
            return clean_int(_text)
        elif mode == 'float':
            return clean_float(_text)
        elif mode == 'user':
            return extract_user_data(source[INDEX[index]])
        
    rows_data = []
    
    target_class = 'ranking-page-table__row'
    
    for tr in rows:
        tr_class = tr.get('class')
        if not tr_class:
            continue
        if target_class not in tr_class:
            continue
        
        tds = tr.find_all('td')
        
        rank       = _get(tds, 'RANK', 'int')
        id, ign    = _get(tds, 'IGN', 'user')
        acc        = _get(tds, 'ACC', 'float')
        pp         = _get(tds, 'PP', 'int')
        play_count = _get(tds, 'PC', 'int')
        rank_x     = _get(tds, 'X', 'int')
        rank_s     = _get(tds, 'S', 'int')
        rank_a     = _get(tds, 'A', 'int')

        rows_data.append({
            'rank'      : rank,
            'id'        : id,
            'ign'       : ign,
            'pp'        : pp,
            'acc'       : acc,
            'play_count': play_count,
            'rank_x'    : rank_x,
            'rank_s'    : rank_s,
            'rank_a'    : rank_a,
        })

    return rows_data

def get_page_rankings(url:str) -> list[dict[str, str]]:
    response = requests.get(url)
    if not response.status_code == 200:
        print(f'[{response.status_code}]: Failed to gather data from {url}\n', end='\r')
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    page_data = extract_data_from_rows(soup.find_all('tr'))
    
    return page_data

def get_rankings(mode:str='osu', country:str=None, pages:str=1) -> list[dict[str, any]]:
    pages = min(pages, 200)

    url = f'https://osu.ppy.sh/rankings/{mode}/performance'

    if country:
        url += f'?country={country}'

    value_mapping = ['rank', 'ign', 'pp', 'acc', 'play_count', 'rank_x', 'rank_s', 'rank_a']
    values_key = 'id'

    def _encode_to_map(map: list[str], data: dict[str, str], key: str) -> tuple[str, list[any]]:
        return data[key], [data[index] for index in map]

    full_data = {
        'update_date': time.time(),
        'mode': mode,
        'country': country if country else 'all',
        'pages': pages,
        'map': value_mapping,
        'data': {},
    }

    for page in range(int(pages)):
        _spage = str(page+1)
        fill = len(str(pages))
        print(f'c: {country} m: {mode} c/f: {_spage.zfill(fill)}/{pages}', end='\r')
        fetch_start_time = time.time()
        
        if country:
            page_url = f'{url}&page={page+1}'
        else:
            page_url = f'{url}?page={page+1}'
        page_data = get_page_rankings(page_url)
        
        time.sleep(0.5)
        
        for data in page_data:
            uid, values = _encode_to_map(value_mapping, data, values_key)
            full_data['data'][uid] = values
        
        fetch_duration = time.time() - fetch_start_time
        print(f'c: {country} m: {mode} c/f: {_spage.zfill(fill)}/{pages} OK: {fetch_duration:.4f}s\n', end="\r")

    return full_data

def dump_to_file(data:list[dict[str, any]], test:bool=False, formatted:bool=False) -> str:
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
    
    parser.add_argument('-m', '--mode', type=str, default='0', help="What game mode to scan for. You can use owo bot's -m params or short hands like ctb, std, etc.")
    parser.add_argument('-p', '--pages', type=int, default=1, help='Number of pages to scan, maximum of 200. Defaults to 1')
    parser.add_argument('-c', '--country', type=str, default=None, help="What country's leaderboard to scan for. Uses the 2 letter system (US, JP, PH, etc.)")
    parser.add_argument('--test', action='store_true', help='Just do tests')
    parser.add_argument('--formatted', action='store_true', help='Make the output .json to be somewhat readable')
    
    args = parser.parse_args()
    
    mode_map = {
        '0': 'osu', 'std': 'osu', 'standard': 'osu', 's': 'osu',
        '1': 'taiko', 'taiko': 'taiko', 'taco': 'taiko', 't': 'taiko',
        '2': 'fruits', 'ctb': 'fruits', 'fruits': 'fruits', 'catch': 'fruits', 'c': 'fruits',
        '3': 'mania', 'mania': 'mania', 'm': 'mania'
    }
    mode = mode_map.get(args.mode)
    if mode is None:
        print(f'This mode: "{args.mode}" is not a valid one. Try again')
        return
    
    data = get_rankings(mode=mode, country=args.country, pages=args.pages)
    output_file = dump_to_file(data, test=args.test, formatted=args.formatted)
    
    print(output_file)

if __name__ == '__main__':
    main()