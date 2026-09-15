import re
from typing import List

from pydantic import BaseModel

from integrations.music_embeds import MusicAddMessage, AddingType
from integrations.music_models import (
    MusicAttributes,
    MusicSource,
    Music,
    MusicAuthor,
    MusicAlbum, MusicQueueItem
)
from yandex_music import Client

class YandexLink(BaseModel):
    type: AddingType
    track_id: str| None = None
    user_id: str|None = None
    playlist_id: str|None = None
    album_id: str|None = None

class YandexResolver:
    def __init__(self, token: str):
        self.token = token
        self.client = Client(token=token).init()

    def _get_artists_str(self, artists) -> str:
        """Вспомогательный метод для корректной сборки имён артистов."""
        if not artists:
            return "Unknown"
        return ", ".join(artist.name for artist in artists if artist.name)

    def find_musics(self, url: str) -> MusicAddMessage:
        """Универсальный поиск треков по ссылке (трек, альбом, плейлист).

        Возвращает список словарей:
        [{'title': str, 'url': str, 'author': str}]
        """
        if "music.yandex.ru" not in url:
            raise ValueError("Неподдерживаемый URL: адрес должен быть с music.yandex.ru")

        link = self._parse_url(url)
        # 1. Проверяем, является ли ссылка отдельным треком
        if link.type == AddingType.TRACK:
            return self._find_track(url,link.track_id)
        elif link.type == AddingType.ALBUM:
            return self._find_album(url,link.album_id)
        elif link.type == AddingType.PLAYLIST:
            return self._find_playlist(url,link.playlist_id,link.user_id)
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

    def _parse_url(self, url: str) -> YandexLink:
        """Определяет тип ссылки Yandex Music и извлекает ID сущностей."""
        if "music.yandex.ru" not in url:
            raise ValueError(
                "Неподдерживаемый URL: адрес должен быть с music.yandex.ru"
            )

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

        raise ValueError(
            "Не удалось распознать тип ссылки (трек, альбом или плейлист)"
        )

    def _build_music_attributes(self, track, page_url: str) -> MusicAttributes:
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
                name=self._get_artists_str(track.artists),
            ),
            album=MusicAlbum(
                name=album_title
            ),
        )

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
            attributes = self._build_music_attributes(track, item_info["url"])
            result_list.append(attributes)

        return result_list

    def get_track_by_url(self, url):

        if "music.yandex.ru" not in url:

            raise FileNotFoundError("Не поддерживаемый url")

        match = re.search(r'track/(\d+)', url)

        if not match:

            raise FileNotFoundError("Не поддерживаемый url")

        track_id = match.group(1)

        track = self.client.tracks([track_id])[0]

        print(track.get_cover_url("50x50"))

        print(f"Загружен трек: {track.title}")

    # Получаем ссылку на поток

        direct_url = track.get_download_info()[0].get_direct_link()

        print(direct_url)

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

                name="".join(artist.name or "" for artist in track.artists),

            ),

            album=MusicAlbum(

            ),

        )

        return music_attributes

