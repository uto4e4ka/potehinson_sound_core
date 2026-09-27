from abc import ABC, abstractmethod

from integrations.music.music_embeds import MusicAddMessage
from integrations.music.music_models import MusicAttributes


class BaseResolver(ABC):

    @abstractmethod
    async def find_musics(self, url: str) -> MusicAddMessage:
        pass


    @abstractmethod
    async def get_track_by_url(self, url) -> MusicAttributes:
        pass

    @abstractmethod
    def can_resolve(self, url) -> bool:
        pass