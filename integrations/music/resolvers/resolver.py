from abc import ABC, abstractclassmethod, abstractmethod
from typing import List

from integrations.music_embeds import MusicAddMessage
from integrations.music_models import MusicAttributes


class BaseResolver(ABC):


    def __init__(self, token: str) -> None:
        """Базовый конструктор, гарантирующий наличие токена.

        Вызывается во всех дочерних классах через super().__init__(token).
        """
        if not token or not isinstance(token, str) or not token.strip():
            raise ValueError(
                f"Для работы {self.__class__.__name__} требуется валидный непустой токен."
            )

        self.token = token.strip()


    @abstractmethod
    def find_musics(self, url: str) -> MusicAddMessage:
        pass


    @abstractmethod
    def get_track_by_url(self, url) -> MusicAttributes:
        pass

    @abstractmethod
    def can_resolve(self, url) -> bool:
        pass