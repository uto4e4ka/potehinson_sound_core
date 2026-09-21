from pathlib import Path

from integrations.music_embeds import MusicAddMessage
from integrations.music_models import MusicAttributes, MusicSource, Music, MusicAuthor, MusicAlbum, MusicGenre
from integrations.resolvers.resolver import BaseResolver
from integrations.resolvers.yandex_resolver import YandexResolver
from mutagen.mp3 import MP3


resolvers = [
    YandexResolver("y0__wgBEOy528ACGN74BiDwr8j-GI_duTInxfTvnpB5XJ7c5I-Io0Gc")
]
def get_tag(tags, key: str) -> str:
    if tags is None:
        return ""
    value = tags.get(key)

    if value is None:
        return ""

    return str(value.text[0]) if value.text else ""



def _get_resolver(url:str)-> BaseResolver:
    for resolver in resolvers:
        if resolver.can_resolve(url):
            return resolver
    raise FileNotFoundError("Данный тип ссылок не поддерживается.")

def get_musics(url:str) -> MusicAddMessage|None:
    resolver = _get_resolver(url)
    return resolver.find_musics(url)

def get_music_by_url(url:str)-> MusicAttributes:
    resolver = _get_resolver(url)
    return resolver.get_track_by_url(url)


