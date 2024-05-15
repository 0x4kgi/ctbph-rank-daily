from bs4 import BeautifulSoup
from bs4.element import Tag
import requests, json

def extract_data_from_row(rows) -> list[list[str]]:
    rows_data = []
    target_class = 'ranking-page-table__row'

    for tr in rows:
        tr_class = tr.get('class')

        if not tr_class:
            continue
        if not target_class in tr_class:
            continue
        tr_data = []

        for desc in tr.descendants:
            if not isinstance(desc, Tag):
                continue
            text = desc.get_text().strip()
            tr_data.append(text)
        rows_data.append(tr_data)

    return rows_data

def get_page_rankings(url: str) -> list[dict[str, str]]:
    response = requests.get(url)
    if not response.status_code == 200:
        print('Cant access ' + url)
        return
    
    soup = BeautifulSoup(response.content, 'html.parser')
    page_data = extract_data_from_row(soup.find_all('tr'))

    player_data = []

    def clean_int(value: str) -> int:
        return int(value.replace(',',''))
    def clean_float(value: str) -> float:
        value = value.replace(',','')
        return(float(value.replace('%', '')))

    for data in page_data:
        # this is so gonna break
        player_data.append({
            'rank': clean_int(data[0][1:]),
            'player': data[1],
            'accuracy': clean_float(data[6]),
            'play_count': clean_int(data[7]),
            'pp': clean_int(data[8]),
            'rank_ss': clean_int(data[9]),
            'rank_s': clean_int(data[10]),
            'rank_a': clean_int(data[11]),
        })

    return player_data

def get_rankings(mode='fruits', country='PH', pages=4) -> list[dict[str, str]]:
    url = f'https://osu.ppy.sh/rankings/{mode}/performance?country={country}'

    full_data = []

    for page in range(int(pages)):
        print(f'Getting page {page+1} / {pages} of the {country} {mode} leaderboards')
        page_url = f'{url}&page={page+1}'
        full_data += get_page_rankings(page_url)
    
    return full_data

if __name__ == '__main__':
    # 200 pages for now
    # stress test lets gooooo
    data = get_rankings(pages=200)
    with open('tests/data.json', 'w') as f:
        json.dump(data, f)