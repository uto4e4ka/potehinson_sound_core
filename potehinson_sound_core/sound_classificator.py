from enum import Enum
from pathlib import Path
from typing import List

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

def format_duration(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    return f"`{minutes}` мин `{seconds:02d}` сек"

async def _extract_dominant_color(url: str) -> int | None:
    """Скачивает обложку и находит преобладающий цвет через квантование (Fast Octree)."""
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return None
                image_data = await resp.read()
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        img.thumbnail((150, 150))
        quantized = img.quantize(colors=5, method=Image.Quantize.FASTOCTREE)
        palette = quantized.getpalette()
        r, g, b = palette[0], palette[1], palette[2]
        return (r << 16) + (g << 8) + b

    except Exception as e:
        print(f"[get_music_embed] Ошибка определения цвета обложки: {e}")
        return None


async def get_music_embed(music_attr: MusicAttributes) -> Embed:
    # 1. Пытаемся получить цвет обложки с помощью квантования
    dominant_color = await _extract_dominant_color(music_attr.music.icon_url)

    # 2. Если не получилось извлечь (или нет icon_url) — берем стандартный розовый
    embed_color = dominant_color if dominant_color is not None else 0xFF69B4

    return Embed(
        title=music_attr.music.name,
        description=music_attr.author.name,
        color=embed_color,
        url=music_attr.music.url,
        author=EmbedAuthor(
            name="Воспроизведение трека",
        ),
        thumbnail=EmbedThumbnail(url=music_attr.music.icon_url),
        footer=EmbedFooter(text=music_attr.source),
        fields=[
            EmbedField(
                name="Длительность",
                value=format_duration(music_attr.duration),
                inline=False,
            ),
        ],
    )

def get_music_attributes(url:str)-> MusicAttributes:
    if not url.startswith(("http://", "https://")):
        return _file_resolver(url)
    if "music.yandex.ru" in url:
        return YandexResolver("y0__wgBEOy528ACGN74BiDwr8j-GI_duTInxfTvnpB5XJ7c5I-Io0Gc").get_track_by_url(url)
    return None

def get_musics(url:str) -> List[MusicQueueItem]:
    if not url.startswith(("http://", "https://")):
        return []
    if "music.yandex.ru" in url:
        return YandexResolver("y0__wgBEOy528ACGN74BiDwr8j-GI_duTInxfTvnpB5XJ7c5I-Io0Gc").find_musics(url)
    return []

def get_music_by_url(url:str)-> MusicAttributes:
    if not url.startswith(("http://", "https://")):
        return None
    if "music.yandex.ru" in url:
        return YandexResolver("y0__wgBEOy528ACGN74BiDwr8j-GI_duTInxfTvnpB5XJ7c5I-Io0Gc").get_track_by_url(url)
    return None

