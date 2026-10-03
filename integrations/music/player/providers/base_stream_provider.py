from abc import ABC, abstractmethod
from collections import deque
from typing import Optional, Dict

from integrations.music.music_models import MusicAttributes, MusicQueueItem
from potehinson_sound_core.core import Core


class BaseStreamProvider(ABC):

    @abstractmethod
    async def next_track(self)->Optional[MusicAttributes]:
        pass

    async def skip_track(self)->Optional[MusicAttributes]:
        pass

    async def prev_track(self)->Optional[MusicAttributes]:
        pass

    def has_previous(self) -> bool:
        """Можно ли отмотать назад прямо сейчас?"""
        return False

    def has_next(self) -> bool:
        """Есть ли следующий трек?"""
        return True