from integrations.music.music_embeds import MusicAddMessage
from integrations.music.music_models import MusicAttributes
from integrations.music.resolvers.resolver import BaseResolver
from integrations.music.resolvers.yandex_resolver import YandexResolver


class MusicFetcher:

    def __init__(self,resolvers:list[BaseResolver]) -> None:
        self.resolvers = resolvers

    def _get_resolver(self,url:str)-> BaseResolver:
        for resolver in self.resolvers:
            if resolver.can_resolve(url):
                return resolver
        raise FileNotFoundError("Данный тип ссылок не поддерживается.")

    def get_musics(self, url:str) -> MusicAddMessage|None:
        resolver = self._get_resolver(url)
        return resolver.find_musics(url)

    def get_music_by_url(self,url:str)-> MusicAttributes:
        resolver = self._get_resolver(url)
        return resolver.get_track_by_url(url)


