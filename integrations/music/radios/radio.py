from abc import ABC, abstractmethod
from typing import Optional

from yandex_music import Track

from integrations.music.music_models import Music, MusicAttributes


class BaseRadio(ABC):

    @abstractmethod
    async def track(self)->Optional[MusicAttributes]:
        pass

    @abstractmethod
    async def skip(self)->Optional[MusicAttributes]:
        pass
