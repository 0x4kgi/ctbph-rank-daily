from bs4 import BeautifulSoup
import requests, json, time

def text(elem) -> str:
    return elem.get_text().strip()

def clean_int(value: str) -> int:
    return int(value.replace(',',''))

def clean_float(value: str) -> float:
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

def get_page_rankings(url: str) -> list[dict[str, str]]:
    response = requests.get(url)
    if not response.status_code == 200:
        print('Cant access ' + url)
        return
    
    soup = BeautifulSoup(response.content, 'html.parser')
    page_data = extract_data_from_rows(soup.find_all('tr'))
    
    return page_data

def get_rankings(mode='fruits', country='PH', pages=1) -> list[dict[str, any]]:
    url = f'https://osu.ppy.sh/rankings/{mode}/performance?country={country}'

    value_mapping = ['rank', 'ign', 'pp', 'acc', 'play_count', 'rank_x', 'rank_s', 'rank_a']
    values_key = 'id'

    def _encode_to_map(map: list[str], data: dict[str, str], key: str) -> tuple[str, list[any]]:
        return data[key], [data[index] for index in map]

    full_data = {
        'update_date': time.time(),
        'map': value_mapping,
        'data': {},
    }

    for page in range(int(pages)):
        print(f'Getting page {page+1} / {pages} of the {country} {mode} leaderboards')
        page_url = f'{url}&page={page+1}'

        page_data = get_page_rankings(page_url)

        for data in page_data:
            uid, values = _encode_to_map(value_mapping, data, values_key)
            full_data['data'][uid] = values
    
    return full_data

if __name__ == '__main__':
    data = get_rankings(pages=1)

    with open('tests/data_pretty-.json', 'w') as f:
        json.dump(data, f, separators=(',', ':'), indent=4)

    with open('tests/data_mini-.json', 'w') as f:
        json.dump(data, f, separators=(',', ':'))