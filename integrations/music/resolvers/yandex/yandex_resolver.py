import re
from typing import List

from loguru import logger
from yandex_music import ClientAsync

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
from integrations.music.resolvers.yandex.utils import _get_artists_str, _build_music_attributes, _parse_url







class YandexResolver(BaseResolver):

    def __init__(self, client:ClientAsync):
        self.client:ClientAsync = client

    def can_resolve(self, url: str) -> bool:
        return any(
            domain in url
            for domain in (
                "music.yandex.ru",
            )
        )

    async def find_musics(self, url: str) -> MusicAddMessage:
        """
        Универсальный поиск треков по ссылке:
        - трек;
        - альбом;
        - плейлист;
        - Моя Волна.
        """

        link = _parse_url(url)

        if link.type == AddingType.TRACK:
            return await self._find_track(
                link.track_id or "",
            )

        if link.type == AddingType.ALBUM:
            return await self._find_album(
                url,
                link.album_id or "",
            )

        if link.type == AddingType.PLAYLIST:
            return await self._find_playlist(
                url,
                link.playlist_id or "",
                link.user_id or "",
            )

        # if link.type == AddingType.WAVE:
            # return get_my_wave_tracks(
            #     client=self.client,
            #     url=link.track_id or "5",
            # )

        raise ValueError(
            "Не удалось распознать тип ссылки "
            "(трек, альбом, плейлист или Моя Волна)"
        )

    async def _find_track(
        self,
        track_id: str,
    ) -> MusicAddMessage:
        results = []

        tracks = await self.client.tracks([track_id])

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

    async def _find_album(
        self,
        url: str,
        album_id: str,
    ) -> MusicAddMessage:
        album = await self.client.albums_with_tracks(album_id)

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

    async def _find_playlist(
        self,
        url: str,
        playlist_id: str,
        user_id: str,
    ) -> MusicAddMessage:
        results = []

        if user_id and playlist_id.isdigit():
            playlist = await self.client.users_playlists(
                playlist_id,
                user_id,
            )
        else:
            playlist = await self.client.playlist(playlist_id)

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

    async def get_tracks_by_url(
        self,
        url: str,
    ) -> List[MusicAttributes]:
        """
        Получает полный список моделей MusicAttributes
        по любой валидной ссылке.
        """

        found_tracks = await self.find_musics(url)

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

        tracks = await self.client.tracks(track_ids)

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

    async def get_track_by_url(
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

        tracks = await self.client.tracks([track_id])

        if not tracks:
            raise FileNotFoundError("Трек не найден")

        track = tracks[0]

        logger.info(f"Загружен трек: {track.title}")

        download_info = await track.get_download_info_async()

        if not download_info:
            raise FileNotFoundError(
                "Не удалось получить информацию для скачивания трека"
            )

        best_info = max(
            download_info,
            key=lambda info: (info.bitrate_in_kbps or 0),
        )

        direct_url = await best_info.get_direct_link_async()

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
                name=album_title or "",
            ),
            quality=AudioQuality.from_bitrate(
                best_info.bitrate_in_kbps
            ),
        )



