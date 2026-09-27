from pathlib import Path

from mutagen.mp3 import MP3

from integrations.music.music_embeds import MusicAddMessage
from integrations.music.music_fetcher import get_tag
from integrations.music.music_models import MusicAttributes, MusicSource, Music, MusicAuthor, MusicAlbum, MusicGenre
from integrations.music.resolvers.resolver import BaseResolver


class FileResolver(BaseResolver):

    def get_tag(tags, key: str) -> str:
        if tags is None:
            return ""
        value = tags.get(key)

        if value is None:
            return ""

        return str(value.text[0]) if value.text else ""

    def get_track_by_url(self, url) -> MusicAttributes:
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

    def can_resolve(self, url) -> bool:
        if "file://" in url:
            return True
        return False

    def find_musics(self, url: str) -> MusicAddMessage:
        pass


