from abc import ABC, abstractmethod
from typing import Optional

from yandex_music import Track

from potehinson_sound_core.music.models import Music, MusicAttributes


class BaseRadio(ABC):

    @abstractmethod
    async def track(self)->Optional[MusicAttributes]:
        pass

    @abstractmethod
    async def skip(self)->Optional[MusicAttributes]:
        pass
