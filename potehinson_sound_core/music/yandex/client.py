import os

from yandex_music import ClientAsync

from potehinson_sound_core.utils import retry


class YandexClientRepo:
    def __init__(self):
        self.async_music_clients:dict[int,ClientAsync] = {}
        pass
    @retry(5,5)
    async def get_async_music_client(self,user_id: int) -> ClientAsync:
        if user_id in self.async_music_clients:
            return self.async_music_clients[user_id]
        self.async_music_clients[user_id] = await ClientAsync(await self.get_user_token(user_id)).init()
        return self.async_music_clients[user_id]

    async def get_user_token(self,user_id: int) -> str:
        return os.environ["YANDEX_TOKEN"]