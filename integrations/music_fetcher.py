from enum import Enum
from pathlib import Path
from typing import List

from integrations.music_embeds import MusicAddMessage
from integrations.music_models import MusicAttributes, MusicSource, Music, MusicAuthor, MusicAlbum, MusicGenre, \
    MusicQueueItem
from integrations.yandex_resolver import YandexResolver
from mutagen.mp3 import MP3
from potehinsonnet.net_models.discord_models import Embed, EmbedImage, EmbedAuthor, EmbedFooter, EmbedThumbnail, \
    EmbedField
from pydantic import BaseModel
import io
import aiohttp
from PIL import Image



def get_tag(tags, key: str) -> str:
    if tags is None:
        return ""
    value = tags.get(key)

    if value is None:
        return ""

    return str(value.text[0]) if value.text else ""

def _file_resolver(url: str) -> MusicAttributes:
    if not url.lower().endswith(".mp3"):
        raise FileNotFoundError("Неподдерживаемый формат аудиофайла. Поддерживаемые форматы:[`.mp3`]")
    audio = MP3(url)
    tags = audio.tags
    return MusicAttributes(
        source=MusicSource.FILE,
        duration=audio.info.length,
        music=Music(
            name=get_tag(tags, "TIT2") or Path(url).stem,
            url=url,
        ),
        author=MusicAuthor(
            name=get_tag(tags, "TPE1") or "Unknown Author",
        ),
        album=MusicAlbum(
            name=get_tag(tags, "TALB"),
        ),
        genre=MusicGenre(
            name=get_tag(tags, "TCON") or "Unknown Genre",
        ),
    )



def get_music_attributes(url:str)-> MusicAttributes:
    if not url.startswith(("http://", "https://")):
        return _file_resolver(url)
    if "music.yandex.ru" in url:
        return YandexResolver("y0__wgBEOy528ACGN74BiDwr8j-GI_duTInxfTvnpB5XJ7c5I-Io0Gc").get_track_by_url(url)
    return None

def get_musics(url:str) -> MusicAddMessage|None:
    if not url.startswith(("http://", "https://")):
        return None
    if "music.yandex.ru" in url:
        musics = YandexResolver("y0__wgBEOy528ACGN74BiDwr8j-GI_duTInxfTvnpB5XJ7c5I-Io0Gc").find_musics(url)
        return musics
    return None


def get_music_by_url(url:str)-> MusicAttributes:
    if not url.startswith(("http://", "https://")):
        return None
    if "music.yandex.ru" in url:
        return YandexResolver("y0__wgBEOy528ACGN74BiDwr8j-GI_duTInxfTvnpB5XJ7c5I-Io0Gc").get_track_by_url(url)
    return None

