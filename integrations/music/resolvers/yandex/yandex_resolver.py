import asyncio
import logging
import re
from typing import List

from aioquic.tls import verify_certificate
from loguru import logger
from pydantic import BaseModel
from yandex_music import Client, Track
from yandex_music.utils.request import Request

from integrations.music.music_embeds import MusicAddMessage, AddingType
from integrations.music.music_models import (
    MusicAttributes,
    MusicSource,
    Music,
    MusicAuthor,
    MusicAlbum,
    MusicQueueItem,
    AudioQuality,
)
from integrations.music.resolvers.resolver import BaseResolver
from integrations.music.resolvers.yandex_radio import RotorClient


class YandexLink(BaseModel):
    type: AddingType
    track_id: str | None = None
    user_id: str | None = None
    playlist_id: str | None = None
    album_id: str | None = None


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


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

class YandexResolver(BaseResolver):

    def __init__(self, token: str):
        super().__init__(token)

        self.token = token
        self.client = Client(token=token).init()
        self.radio = RotorClient(client=self.client)

    def can_resolve(self, url: str) -> bool:
        return any(
            domain in url
            for domain in (
                "music.yandex.ru",
                "yandex_wave:",
            )
        )

    def find_musics(self, url: str) -> MusicAddMessage:
        """
        Универсальный поиск треков по ссылке:
        - трек;
        - альбом;
        - плейлист;
        - Моя Волна.
        """

        link = _parse_url(url)

        if link.type == AddingType.TRACK:
            return self._find_track(
                url,
                link.track_id or "",
            )

        if link.type == AddingType.ALBUM:
            return self._find_album(
                url,
                link.album_id or "",
            )

        if link.type == AddingType.PLAYLIST:
            return self._find_playlist(
                url,
                link.playlist_id or "",
                link.user_id or "",
            )

        if link.type == AddingType.WAVE:
            return self.get_my_wave_tracks(
                link.track_id or "5"
            )

        raise ValueError(
            "Не удалось распознать тип ссылки "
            "(трек, альбом, плейлист или Моя Волна)"
        )

    def _find_track(
        self,
        url: str,
        track_id: str,
    ) -> MusicAddMessage:
        results = []

        tracks = self.client.tracks([track_id])

        if not tracks:
            raise FileNotFoundError("Трек не найден")

        track = tracks[0]

        results.append(
            MusicQueueItem(
                music=Music(
                    name=track.title or "Unknown",
                    url=(
                        f"https://music.yandex.ru/album/"
                        f"{track.albums[0].id if track.albums else '0'}"
                        f"/track/{track.id}"
                    ),
                )
            )
        )

        return MusicAddMessage(
            add_type=AddingType.TRACK,
            source=MusicSource.YANDEX_MUSIC,
            name=track.title or "Unknown",
            count=len(results),
            icon_url=track.get_cover_url("150x150"),
            music_list=results,
        )

    def _find_album(
        self,
        url: str,
        album_id: str,
    ) -> MusicAddMessage:
        album = self.client.albums_with_tracks(album_id)

        results = []

        if album and album.volumes:
            for volume in album.volumes:
                for track in volume:
                    results.append(
                        MusicQueueItem(
                            music=Music(
                                name=track.title or "Unknown",
                                url=(
                                    f"https://music.yandex.ru/album/"
                                    f"{album_id}/track/{track.id}"
                                ),
                            )
                        )
                    )

            return MusicAddMessage(
                music_list=results,
                name=album.title or "Unknown",
                count=len(results),
                source=MusicSource.YANDEX_MUSIC,
                add_type=AddingType.ALBUM,
                icon_url=album.get_og_image_url(size="150x150"),
                url=url,
            )

        raise FileNotFoundError("Альбом не найден")

    def _find_playlist(
        self,
        url: str,
        playlist_id: str,
        user_id: str,
    ) -> MusicAddMessage:
        results = []

        if user_id and playlist_id.isdigit():
            playlist = self.client.users_playlists(
                playlist_id,
                user_id,
            )
        else:
            playlist = self.client.playlist(playlist_id)

        if playlist and playlist.tracks:
            for track_short in playlist.tracks:
                track = track_short.track

                if not track:
                    continue

                album_id = (
                    track.albums[0].id
                    if track.albums
                    else "0"
                )

                results.append(
                    MusicQueueItem(
                        music=Music(
                            name=track.title or "Unknown",
                            url=(
                                f"https://music.yandex.ru/album/"
                                f"{album_id}/track/{track.id}"
                            ),
                        )
                    )
                )

            return MusicAddMessage(
                music_list=results,
                name=playlist.title or "Unknown",
                count=len(results),
                source=MusicSource.YANDEX_MUSIC,
                add_type=AddingType.PLAYLIST,
                icon_url=playlist.cover.get_url(size="150x150") if playlist.cover else "",
                url=url,
            )

        raise FileNotFoundError("Плейлист не найден")

    def get_tracks_by_url(
        self,
        url: str,
    ) -> List[MusicAttributes]:
        """
        Получает полный список моделей MusicAttributes
        по любой валидной ссылке.
        """

        found_tracks = self.find_musics(url)

        if not found_tracks:
            return []

        track_ids = []

        for item in found_tracks.music_list:
            match = re.search(
                r"track/(\d+)",
                item.music.url,
            )

            if match:
                track_ids.append(match.group(1))

        if not track_ids:
            return []

        tracks = self.client.tracks(track_ids)

        result_list = []

        for track, item_info in zip(
            tracks,
            found_tracks.music_list,
        ):
            attributes = _build_music_attributes(
                track,
                item_info.music.url,
            )

            result_list.append(attributes)

        return result_list

    def get_track_by_url(
        self,
        url: str,
    ) -> MusicAttributes:
        if "music.yandex.ru" not in url:
            raise FileNotFoundError("Не поддерживаемый url")

        match = re.search(
            r"track/(\d+)",
            url,
        )

        if not match:
            raise FileNotFoundError("Не поддерживаемый url")

        track_id = match.group(1)

        tracks = self.client.tracks([track_id])

        if not tracks:
            raise FileNotFoundError("Трек не найден")

        track = tracks[0]

        logger.info(f"Загружен трек: {track.title}")

        download_info = track.get_download_info()

        if not download_info:
            raise FileNotFoundError(
                "Не удалось получить информацию для скачивания трека"
            )

        best_info = max(
            download_info,
            key=lambda info: (info.bitrate_in_kbps or 0),
        )

        direct_url = best_info.get_direct_link()

        album_title = (
            track.albums[0].title
            if track.albums
            else ""
        )

        return MusicAttributes(
            source=MusicSource.YANDEX_MUSIC,
            duration=(track.duration_ms or 0) / 1000,
            music=Music(
                name=track.title or "Unknown",
                track_url=direct_url,
                url=url,
                icon_url=track.get_cover_url("100x100"),
            ),
            author=MusicAuthor(
                name=_get_artists_str(track.artists),
            ),
            album=MusicAlbum(
                name=album_title,
            ),
            quality=AudioQuality.from_bitrate(
                best_info.bitrate_in_kbps
            ),
        )

    def get_my_wave_tracks(
        self,
        url: str,
    ) -> MusicAddMessage:
        """
        Получает порцию рекомендованных треков из Моей Волны.
        url содержит количество треков (например: yandex_wave:5).
        """

        station_id = "user:onyourwave"

        try:
            target_count = int(url)
        except ValueError:
            target_count = 5

        logger.info(f"Ищем треки Моей Волны в количестве: {target_count}")

        result_list: List[MusicQueueItem] = []
        queue = None

        while len(result_list) < target_count:
            try:
                rotor_result = self.client.rotor_station_tracks(
                    station_id,
                    queue=queue,
                )

                tracks_info = rotor_result.sequence
                batch_id = getattr(rotor_result, "batch_id", None)

                # Безопасный вызов инициализации радиосессии
                if batch_id:
                    try:
                        self.client.rotor_station_feedback_radio_started(
                            station="RNjY-zj5dHuJI3V0SRi-PzsU",
                            from_="desktop-wave_landing_screen-my_wave-radio-default",
                            timestamp="2026-09-22T02:54:46.000Z"

                        )
                        logger.info(
                            f"Яндекс feedback [radioStarted] отправлен: batch_id={batch_id}"
                        )
                    except Exception as fb_err:
                        logger.warning(
                            f"Предупреждение при отправке radioStarted: {fb_err}"
                        )

                if not tracks_info:
                    logger.warning("Яндекс Музыка не вернула больше треков.")
                    break

                logger.debug(
                    f"Получен batch Моей Волны: batch_id={batch_id}, tracks={len(tracks_info)}"
                )

                for item in tracks_info:
                    if len(result_list) >= target_count:
                        break

                    track: Track = item.track

                    if not track:
                        continue

                    album_id = (
                        str(track.albums[0].id)
                        if track.albums
                        else None
                    )

                    page_url = (
                        f"https://music.yandex.ru/album/"
                        f"{album_id or '0'}/track/{track.id}"
                    )

                    try:

                        queue_item = MusicQueueItem(
                            music=Music(
                                name=track.title or "Unknown",
                                url=page_url,
                                feedback_callback=self._make_feedback_callback(
                                    station_id=station_id,
                                    track_id=str(track.id),
                                    album_id=album_id,
                                    batch_id=batch_id,
                                ),
                            )
                        )

                        result_list.append(queue_item)

                    except Exception as err:
                        logger.warning(
                            f"Не удалось обработать трек {track.id}: {err}"
                        )
                        continue

                queue = [
                    item.track.id
                    for item in tracks_info
                    if item.track
                ]

            except Exception as e:
                logger.error(f"Ошибка при получении батча треков Моей Волны: {e}")

                if not result_list:
                    raise FileNotFoundError(
                        f"Ошибка при получении треков Моей Волны: {e}"
                    )

                break

        return MusicAddMessage(
            add_type=AddingType.WAVE,
            source=MusicSource.YANDEX_MUSIC,
            name="Моя волна",
            music_list=result_list,
            count=len(result_list),
        )

    def _make_feedback_callback(
        self,
        station_id: str,
        track_id: str,
        album_id: str | None = None,
        batch_id: str | None = None,
    ):
        """
        Создаёт индивидуальный callback для трека Моей Волны.

        События:
            start  -> trackStarted
            finish -> trackFinished
            skip   -> skip
        """

        async def callback(
            event_type: str,
            played_seconds: float,
        ):
            try:
                if event_type == "start":
                    await asyncio.to_thread(
                        self._send_track_started,
                        station_id,
                        track_id,
                        batch_id,
                    )

                    logger.info(
                        f"Яндекс feedback [trackStarted] отправлен для трека {track_id}"
                    )

                elif event_type == "finish":
                    await asyncio.to_thread(
                        self._send_track_finished,
                        station_id,
                        track_id,
                        played_seconds,
                        batch_id,
                    )

                    logger.info(
                        f"Яндекс feedback [trackFinished] отправлен для трека {track_id}"
                    )

                elif event_type == "skip":
                    await asyncio.to_thread(
                        self._send_skip,
                        station_id,
                        track_id,
                        played_seconds,
                        batch_id,
                    )

                    logger.info(
                        f"Яндекс feedback [skip] отправлен для трека {track_id}"
                    )

                else:
                    logger.debug(f"Неизвестный тип feedback: {event_type}")

            except Exception as e:
                logger.warning(
                    f"Ошибка при отправке фидбека {event_type} в Яндекс: {e}"
                )

        return callback

    def _send_track_started(
        self,
        station_id: str,
        track_id: str,
        batch_id: str | None,
    ):
        """Отправка trackStarted."""
        try:
            logger.debug(f"Try to start session {track_id} {batch_id} {station_id}")
            self.radio.track_started(
                station=station_id,
                track_id=track_id,
                batch_id=batch_id,
            )
        except Exception as e:
            logger.debug(f"Игнорируем ошибку trackStarted ({e})")

    def _send_track_finished(
        self,
        station_id: str,
        track_id: str,
        played_seconds: float,
        batch_id: str | None,
    ):
        """Отправка trackFinished."""
        try:
            self.radio.track_finished(
                station=station_id,
                track_id=track_id,
                total_played_seconds=float(played_seconds),
                batch_id=batch_id,

            )
        except Exception as e:
            logger.debug(f"Игнорируем ошибку trackFinished ({e})")

    def _send_skip(
        self,
        station_id: str,
        track_id: str,
        played_seconds: float,
        batch_id: str | None,
    ):
        """Отправка skip."""
        try:
            self.radio.skip(
                station=station_id,
                track_id=track_id,
                total_played_seconds=float(played_seconds),
                batch_id=batch_id,

            )
        except Exception as e:
            logger.debug(f"Игнорируем ошибку skip ({e})")