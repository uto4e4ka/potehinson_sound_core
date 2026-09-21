import re
from typing import List

from loguru import logger
from pydantic import BaseModel

from integrations.music.music_embeds import MusicAddMessage, AddingType
from integrations.music.music_models import (
    MusicAttributes,
    MusicSource,
    Music,
    MusicAuthor,
    MusicAlbum, MusicQueueItem
)
from yandex_music import Client, Track

from integrations.music.resolvers.resolver import BaseResolver


class YandexLink(BaseModel):
    type: AddingType
    track_id: str| None = None
    user_id: str|None = None
    playlist_id: str|None = None
    album_id: str|None = None


def _get_artists_str(artists) -> str:
    """Вспомогательный метод для корректной сборки имён артистов."""
    if not artists:
        return "Unknown"
    return ", ".join(artist.name for artist in artists if artist.name)


def _parse_url(url: str) -> YandexLink:
    """Определяет тип ссылки Yandex Music и извлекает ID сущностей."""

    # 1. Трек
    track_match = re.search(r"track/(\d+)", url)
    if track_match:
        return YandexLink(
            type=AddingType.TRACK, track_id=track_match.group(1)
        )

    # 2. Альбом
    album_match = re.search(r"album/(\d+)", url)
    if album_match and "track" not in url:
        return YandexLink(
            type=AddingType.ALBUM, album_id=album_match.group(1)
        )

    # 3. Плейлист
    playlist_match = re.search(r"(?:users/([^/]+)/)?playlists/([\w-]+)", url)
    if playlist_match:
        return YandexLink(
            type=AddingType.PLAYLIST,
            user_id=playlist_match.group(1),
            playlist_id=playlist_match.group(2),
        )

    wave_match = re.match(r"^yandex_wave:(\d+)$", url)
    if wave_match:
        return YandexLink(
            type=AddingType.WAVE,
            track_id=wave_match.group(1),
        )

    raise ValueError(
        "Не удалось распознать тип ссылки (трек, альбом или плейлист)"
    )


def _build_music_attributes(track, page_url: str) -> MusicAttributes:
    """Сборка объекта MusicAttributes из сущности Track."""
    download_info = track.get_download_info()
    direct_url = download_info[0].get_direct_link() if download_info else ""

    album_title = track.albums[0].title if track.albums else None

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
            name=album_title or ""
        ),
    )


class YandexResolver(BaseResolver):



    def __init__(self, token: str):
        super().__init__(token)
        self.token = token
        self.client = Client(token=token).init()


    def can_resolve(self, url) -> bool:
        if any(domain in url for domain in ("music.yandex.ru", "yandex_wave:")):
            return True
        return False


    def find_musics(self, url: str) -> MusicAddMessage:
        """Универсальный поиск треков по ссылке (трек, альбом, плейлист).

        Возвращает список словарей:
        [{'title': str, 'url': str, 'author': str}]
        """


        link = _parse_url(url)
        # 1. Проверяем, является ли ссылка отдельным треком
        if link.type == AddingType.TRACK:
            return self._find_track(url,link.track_id or "")
        elif link.type == AddingType.ALBUM:
            return self._find_album(url,link.album_id or "")
        elif link.type == AddingType.PLAYLIST:
            return self._find_playlist(url,link.playlist_id or "",link.user_id or "")
        elif link.type == AddingType.WAVE:
            return self.get_my_wave_tracks(link.track_id or "0")
        else:
            raise ValueError("Не удалось распознать тип ссылки (трек, альбом или плейлист)")

    def _find_track(self,url:str,track_id:str)->MusicAddMessage:
        results = []
        tracks = self.client.tracks([track_id])
        if not tracks:
            raise FileNotFoundError("Трек не найден")
        track = tracks[0]
        results.append(MusicQueueItem(
            music=Music(
                name=track.title or "Unknown",
                url=f"https://music.yandex.ru/album/{track.albums[0].id if track.albums else '0'}/track/{track.id}",

            )
        )
        )
        return MusicAddMessage(
            add_type=AddingType.TRACK,
            source=MusicSource.YANDEX_MUSIC,
            name=track.title or "Unknown",
            count=len(results),
            icon_url=track.getCoverUrl(size="150x150"),
            music_list=results
        )

    def _find_album(self,url:str,album_id:str)->MusicAddMessage:
        album = self.client.albums_with_tracks(album_id)
        results = []
        if album and album.volumes:
            for volume in album.volumes:
                for track in volume:
                    results.append(MusicQueueItem(
                        music=Music(
                            name=track.title or "Unknown",
                            url=f"https://music.yandex.ru/album/{album_id}/track/{track.id}",

                        )
                    )
                    )
            return MusicAddMessage(
                music_list= results,
                name=album.title or "Unknown",
                count=len(results),
                source=MusicSource.YANDEX_MUSIC,
                add_type=AddingType.ALBUM,
                icon_url=album.get_og_image_url(size="150x150"),
                url=url
            )
        raise FileNotFoundError("Альбом не найден")

    def _find_playlist(self,url:str,playlist_id:str,user_id:str)->MusicAddMessage:
        results = []
        if user_id and playlist_id.isdigit():
            playlist = self.client.users_playlists(playlist_id, user_id)
        else:
            playlist = self.client.playlist(playlist_id)

        if playlist and playlist.tracks:
            for track_short in playlist.tracks:
                track = track_short.track
                if not track:
                    continue

                album_id = track.albums[0].id if track.albums else "0"
                results.append(MusicQueueItem(
                    music=Music(
                        name=track.title or "Unknown",
                        url=f"https://music.yandex.ru/album/{album_id}/track/{track.id}",

                    )
                ))
            return MusicAddMessage(
                music_list= results,
                name=playlist.title or "Unknown",
                count=len(results),
                source=MusicSource.YANDEX_MUSIC,
                add_type=AddingType.PLAYLIST,
                icon_url=playlist.cover.get_url(size="150x150"),
                url=url
            )
        raise FileNotFoundError("Плейлист не найден")

    def get_tracks_by_url(self, url: str) -> List[MusicAttributes]:
        """Получает полный список моделей MusicAttributes по любой валидной ссылке."""
        found_tracks = self.find_musics(url)
        if not found_tracks:
            return []

        # Собираем все ID треков для получения данных единым батч-запросом
        track_ids = []
        for item in found_tracks:
            match = re.search(r'track/(\d+)', item["url"])
            if match:
                track_ids.append(match.group(1))

        if not track_ids:
            return []

        # Запрашиваем данные треков из Yandex API (до 1000 за раз)
        tracks = self.client.tracks(track_ids)
        result_list = []

        for track, item_info in zip(tracks, found_tracks):
            attributes = _build_music_attributes(track, item_info["url"])
            result_list.append(attributes)

        return result_list

    def get_track_by_url(self, url) -> MusicAttributes:

        print(self.get_my_wave_tracks(10))

        if "music.yandex.ru" not in url:

            raise FileNotFoundError("Не поддерживаемый url")

        match = re.search(r'track/(\d+)', url)

        if not match:

            raise FileNotFoundError("Не поддерживаемый url")

        track_id = match.group(1)

        track = self.client.tracks([track_id])[0]

        logger.info(f"Загружен трек: {track.title}")


        download_info = track.get_download_info()

        best_info = max(
            download_info,
            key=lambda info: info.bitrate_in_kbps or 0
        )

        direct_url = best_info.get_direct_link()

        music_attributes = MusicAttributes(

            source=MusicSource.YANDEX_MUSIC,

            duration=track.duration_ms / 1000,

            music=Music(

                name=track.title or "Unknown",

                track_url=direct_url,

                url=url,

                icon_url=track.get_cover_url("100x100"),

            ),

            author=MusicAuthor(

                name="".join((artist.name or "")+", " for artist in track.artists),

            ),

            album=MusicAlbum(

            ),

        )

        return music_attributes

    def get_my_wave_tracks(self, url: str) -> MusicAddMessage:
        """Получает порцию рекомендованных треков из Моей Волны (станция 'user:onyourwave')."""
        station_id = "user:onyourwave"

        # Парсим количество из URL/строки (например, "15" из "yandex_wave:15")
        try:
            target_count = int(url)
        except ValueError:
            target_count = 5  # Дефолтное значение, если не удалось распарсить

        logger.info(f"Ищем треки Моей волны в количестве: {target_count}")

        result_list: List[MusicQueueItem] = []
        queue = None  # В первой итерации queue передавать не нужно

        # Запрашиваем батчи по 5 треков, пока не наберём нужные target_count
        while len(result_list) < target_count:
            try:
                rotor_result = self.client.rotor_station_tracks(station_id, queue=queue)
                tracks_info = rotor_result.sequence

                if not tracks_info:
                    logger.warning("Яндекс Музыка не вернула больше треков.")
                    break

                for item in tracks_info:
                    if len(result_list) >= target_count:
                        break

                    track: Track = item.track
                    if not track:
                        continue

                    album_id = track.albums[0].id if track.albums else "0"
                    page_url = f"https://music.yandex.ru/album/{album_id}/track/{track.id}"

                    try:
                        queue_item = MusicQueueItem(
                            music=Music(
                                name=track.title or "Unknown",
                                url=page_url
                            )
                        )
                        result_list.append(queue_item)
                    except Exception as err:
                        logger.warning(f"Не удалось обработать трек {track.id}: {err}")
                        continue

                # Формируем queue из ID полученных треков для запроса следующей порции
                queue = [item.track.id for item in tracks_info if item.track]

            except Exception as e:
                logger.error(f"Ошибка при получении батча треков Моей Волны: {e}")
                if not result_list:
                    raise FileNotFoundError(f"Ошибка при получении треков Моей Волны: {e}")
                break  # Если уже что-то набрали, отдаём то, что успели получить

        return MusicAddMessage(
            add_type=AddingType.WAVE,
            source=MusicSource.YANDEX_MUSIC,
            name="Моя волна",
            music_list=result_list,
            count=len(result_list),
        )