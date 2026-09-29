import time
from datetime import datetime, timezone
from typing import Optional

from yandex_music import Track

from integrations.music.music_models import MusicAttributes, Music, MusicAlbum, MusicSource, MusicAuthor, AudioQuality, \
    PlayingType
from integrations.music.resolvers.yandex.utils import get_track_page_url


def get_formatted_track_id(track) -> str:
    track_id = getattr(track, 'real_id', track.id)
    album_id = track.albums[0].id if track.albums else "0"
    return f"{track_id}:{album_id}"

def get_time()->str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def get_played_time(start_time: float) -> float:
    """Возвращает количество проигранных секунд текущего трека."""
    if not start_time:
        return 0.0
    return round(time.time() - start_time, 2)

async def get_track_url(track: Track) -> tuple[str,int]:
    links = await track.get_download_info_async()
    if not links:
        raise FileNotFoundError(
            "Не удалось получить информацию для скачивания трека"
        )

    best_info = max(
        links,
        key=lambda info: (info.bitrate_in_kbps or 0),
    )
    return await best_info.get_direct_link_async(),best_info.bitrate_in_kbps

async def dump_music_model(track:Track)->MusicAttributes:
    info = await get_track_url(track)
    direct_url, bitrate = info
    music = Music(
       name=track.title or "",
       url=get_track_page_url(track.albums[0].id,track.id),
        track_url=  direct_url,
        icon_url=track.get_cover_url("100x100")
    )
    album = MusicAlbum(
        name = track.albums[0].title or "")
    author = MusicAuthor(
        name = ", ".join(artist.name or "" for artist in track.artists)
    )
    return MusicAttributes(
        source=MusicSource.YANDEX_MUSIC,
        duration=track.duration_ms/1000,
        music=music,
        album=album,
        quality=AudioQuality.from_bitrate(bitrate),
        author = author,
        playing_type=PlayingType.WAVE,
    )
