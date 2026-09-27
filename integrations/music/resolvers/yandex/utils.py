import re
from datetime import datetime, timezone
from typing import Optional

from yandex_music import Track

from integrations.music.music_embeds import AddingType
from integrations.music.music_models import MusicAttributes, MusicSource, MusicAuthor, Music, MusicAlbum
from integrations.music.resolvers.yandex.models import YandexLink


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
        r"(?:users/([^/]+)/)?playlists/([\w-]+)",
        url,
    )

    if playlist_match:
        return YandexLink(
            type=AddingType.PLAYLIST,
            user_id=playlist_match.group(1),
            playlist_id=playlist_match.group(2),
        )

    # 4. Моя Волна
    wave_match = re.match(r"^yandex_wave:(\d+)$", url)

    if wave_match:
        return YandexLink(
            type=AddingType.WAVE,
            track_id=wave_match.group(1),
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