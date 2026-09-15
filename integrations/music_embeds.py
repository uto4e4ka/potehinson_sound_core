import io
from enum import Enum

import aiohttp
from PIL import Image
from potehinsonnet.net_models.discord_models import Embed, EmbedFooter, EmbedField, EmbedAuthor, EmbedThumbnail
from pydantic import BaseModel

from integrations.music_models import MusicAttributes, MusicSource, MusicQueueItem


class AddingType(str, Enum):
    ALBUM = "Добавлен альбом"
    TRACK = "Добавлен трек"
    ARTIST = "Добавлены треки исполнителя"
    PLAYLIST = "Добавлен плейлист"

class MusicAddMessage(BaseModel):
    add_type:AddingType
    source:MusicSource
    name:str
    url:str = ""
    icon_url:str = ""
    count:int = 1
    queue_count:int = 0
    music_list:list[MusicQueueItem] = []


def get_add_embed(message: MusicAddMessage) -> Embed:
    embed = Embed(
        title=message.name,
        url=message.url,
        author=EmbedAuthor(
            name= message.add_type
        ),
        thumbnail= EmbedThumbnail(url=message.icon_url),
        fields=[
            EmbedField(
                name= "Добавлено треков",
                value= str(message.count)

            ),
            EmbedField(
                name="Всего в очереди",
                value= str(message.queue_count)
            )
        ],
        footer=EmbedFooter(text=message.source),

    )
    return embed

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