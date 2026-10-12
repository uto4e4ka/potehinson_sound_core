import re
import time
from datetime import datetime, timezone
from typing import Optional

from yandex_music import Track

from potehinson_sound_core.music.embeds import AddingType
from potehinson_sound_core.music.models import MusicAttributes, MusicSource, MusicAuthor, Music, MusicAlbum, \
    AudioQuality, PlayingType
from potehinson_sound_core.music.yandex.models import YandexLink


def _get_artists_str(artists) -> str:
    """Вспомогательный метод для корректной сборки имён артистов."""
    if not artists:
        return "Unknown"

    return ", ".join(
        artist.name
        for artist in artists
        if artist.name
    )


def _parse_url(url: str) -> YandexLink:
    """Определяет тип ссылки Yandex Music и извлекает ID сущностей."""

    # 1. Трек
    track_match = re.search(r"track/(\d+)", url)
    if track_match:
        return YandexLink(
            type=AddingType.TRACK,
            track_id=track_match.group(1),
        )

    # 2. Альбом
    album_match = re.search(r"album/(\d+)", url)
    if album_match and "track" not in url:
        return YandexLink(
            type=AddingType.ALBUM,
            album_id=album_match.group(1),
        )

    # 3. Плейлист
    playlist_match = re.search(
        r"(?:users/([^/]+)/)?playlists/([\w.-]+)",
        url,
    )

    if playlist_match:
        return YandexLink(
            type=AddingType.PLAYLIST,
            user_id=playlist_match.group(1),
            playlist_id=playlist_match.group(2),
        )

    author_match = re.search(r"artist/(\d+)", url)
    if author_match:
        return YandexLink(
            type=AddingType.AUTHOR,
            user_id=author_match.group(1),
        )
    # 4. Моя Волна
    wave_match = re.match(r"^yandex_wave:(\d+)$", url)

    if wave_match:
        return YandexLink(
            type=AddingType.WAVE,
            track_id=wave_match.group(1),
        )

    return YandexLink(
        type=AddingType.SEARCH,
        track_id=url,
    )
    raise ValueError(
        "Не удалось распознать тип ссылки "
        "(трек, альбом, плейлист или Моя Волна)"
    )


def _build_music_attributes(
    track: Track,
    page_url: str,
) -> MusicAttributes:
    """Сборка объекта MusicAttributes из сущности Track."""

    download_info = track.get_download_info()

    direct_url = (
        download_info[0].get_direct_link()
        if download_info
        else ""
    )

    album_title = (
        track.albums[0].title
        if track.albums
        else None
    )

    return MusicAttributes(

        source=MusicSource.YANDEX_MUSIC,
        duration=(track.duration_ms or 0) / 1000,
        music=Music(
            id= track.id,
            name=track.title or "Unknown",
            track_url=direct_url,
            url=page_url,
            icon_url=track.get_cover_url("100x100"),
        ),
        author=MusicAuthor(
            name=_get_artists_str(track.artists),
        ),
        album=MusicAlbum(
            name=album_title or "",
        ),
    )

def get_track_page_url(album_id:Optional[str|int],track_id:Optional[str|int]) -> str:
    return f"https://music.yandex.ru/album/{album_id}/track/{track_id}"


# ============================================================
# Моя волна
# ============================================================

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
        id=track.id,
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
