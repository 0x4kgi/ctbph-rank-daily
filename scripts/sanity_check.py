import os
import requests
from dotenv import load_dotenv
from ossapi import Ossapi, UserLookupKey


def main():
    load_dotenv()

    webhook_url = os.getenv('WEBHOOK_URL')
    client_id = os.getenv('OSU_CLIENT_ID')
    client_secret = os.getenv('OSU_CLIENT_SECRET')

    api = Ossapi(client_id, client_secret)

    user = api.user('eoneru', key=UserLookupKey.USERNAME)

    uid = user.id

    correct_id = 'Yes' if 9025855 == uid else 'No'

    payload = {
        'username': 'Correct webhook URL!',
        'avatar_url': user.avatar_url,
        'content': f'Is the api keys for osu! correct?\nResponse: **{correct_id}**',
    }

    response = requests.post(
        webhook_url,
        json=payload
    )

    if response.status_code == 204:
        print('sent')
    else:
        print('not sent: ' + response.status_code)


if __name__ == '__main__':
    main()
