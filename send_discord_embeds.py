from ossapi import Ossapi, Score
from data_to_html import get_data_at_date
from dotenv import load_dotenv
import os, requests

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

def get_recent_toplay_of_user(api:Ossapi, user_id, limit=5) -> Score:
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

def send_embed(content:str, embeds:list):
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

def main():
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')
    api = Ossapi(client_id, client_secret)
    
    users = [
        # just for testing for now, me and top 4 ph
        9025855, 829284, 16355636, 6829103, 1626093
    ]

    for u in users:
        score = get_recent_toplay_of_user(api, u)
        embed = create_embed_from_play(score)
        send_embed(
            content=f'Most recent top play',
            embeds=[embed]
        )

if __name__ == '__main__':
    load_dotenv()
    main()