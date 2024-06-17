import os
import requests
from typing import TypedDict, NotRequired
from scripts.logging_config import logger

class EmbedAuthor(TypedDict):
    name: NotRequired[str]
    url: NotRequired[str]
    icon_url: NotRequired[str]

class EmbedField(TypedDict):
    name: str
    value: str
    inline: NotRequired[bool]

class EmbedFooter(TypedDict):
    text: NotRequired[str]
    icon_url: NotRequired[str]
    inline: NotRequired[bool]

class EmbedImage(TypedDict):
    url: str

class Embed(TypedDict):
    title: str
    description: str
    url: str
    color: int
    fields: list[EmbedField]
    author: EmbedAuthor
    footer: EmbedFooter
    timestamp: str
    image: EmbedImage
    thumbnail: EmbedImage

def embed_maker(
    title:str=None,
    description:str=None,
    url:str=None,
    color:int=None,
    fields:list[EmbedField]=None,
    author:EmbedAuthor=None,
    footer:EmbedFooter=None,
    timestamp:str=None,
    image:EmbedImage=None,
    thumbnail:EmbedImage=None,
) -> Embed:
    return {
        key: value for key, value in locals().items() if value is not None
    }

def send_webhook(
    content:str=None,
    embeds:list[Embed]=[],
    username:str=None,
    avatar_url:str=None
):
    webhook_url = os.getenv('WEBHOOK_URL')

    if webhook_url is None:
        logger.error('No webhook url found. Not sending anything.')
        return

    payload = {
        'username': username,
        'avatar_url': avatar_url,
        'embeds': embeds,
        'content': content,
    }

    response = requests.post(
        webhook_url,
        json=payload
    )

    if response.status_code == 204:
        logger.info(f'Webhook sent. [[ {username} ]]')
    else:
        logger.error(f'Failed to send webhook. Status code: {response.status_code}')