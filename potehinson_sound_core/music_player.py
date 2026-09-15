import asyncio
from collections import deque
from typing import Awaitable, Callable, Dict, List

from potehinsonnet.net_models.discord_models import Embed

from exeptions.playing_execptions import PlayingException
from integrations.music_embeds import get_add_embed
from integrations.music_models import MusicAttributes, MusicQueueItem
from integrations import music_fetcher
from potehinson_sound_core.core import Core
from loguru import logger
TrackChangeCallback = Callable[[int, int, MusicAttributes], Awaitable[None]]
TrackEndCallback = Callable[[int, int, MusicAttributes], Awaitable[None]]


class MusicPlayer:

    def __init__(self, core: Core) -> None:
        self.queue: Dict[int, deque[MusicQueueItem]] = {}
        self.core = core
        self._player_tasks: Dict[int, asyncio.Task] = {}
        self._track_finished_events: Dict[int, asyncio.Event] = {}

        self._track_change_listeners: List[TrackChangeCallback] = []
        self._track_end_listeners: List[TrackEndCallback] = []
        self._pause_events: Dict[int, asyncio.Event] = {}

    def _get_pause_event(self, guild_id: int) -> asyncio.Event:
        """Возвращает Event паузы. По умолчанию set() = не на паузе."""
        if guild_id not in self._pause_events:
            event = asyncio.Event()
            event.set()  # Изначально воспроизведение разрешено
            self._pause_events[guild_id] = event
        return self._pause_events[guild_id]

    async def pause_track(self, guild_id: int) -> bool:
        """Ставит воспроизведение на паузу."""
        pause_event = self._get_pause_event(guild_id)
        if pause_event.is_set():
            pause_event.clear()  # Блокируем дальнейшее продвижение цикла
            try:
                #await self.core.pause_sound(guild_id=guild_id)
                pass
            except Exception as e:
                print(f"[MusicPlayer] Ошибка при паузе в core: {e}")
            return True
        return False

    async def resume_track(self, guild_id: int) -> bool:
        """Снимает воспроизведение с паузы."""
        pause_event = self._get_pause_event(guild_id)
        if not pause_event.is_set():
            pause_event.set()  # Снимаем блокировку
            try:
                #await self.core.resume_sound(guild_id=guild_id)
                pass
            except Exception as e:
                print(f"[MusicPlayer] Ошибка при возобновлении в core: {e}")
            return True
        return False

    def on_track_change(self, callback: TrackChangeCallback):
        self._track_change_listeners.append(callback)

    def on_track_end(self, callback: TrackEndCallback):
        self._track_end_listeners.append(callback)

    async def _notify_track_change(
        self, guild_id: int, text_channel_id: int, item: MusicAttributes
    ):
        for listener in self._track_change_listeners:
            try:
                await listener(guild_id, text_channel_id, item)
            except Exception as e:
                print(f"[MusicPlayer] Ошибка в listener (start): {e}")

    async def _notify_track_end(
        self, guild_id: int, text_channel_id: int, item: MusicAttributes
    ):
        for listener in self._track_end_listeners:
            try:
                await listener(guild_id, text_channel_id, item)
            except Exception as e:
                print(f"[MusicPlayer] Ошибка в listener (end): {e}")

    async def add_music(
        self, url: str, guild_id: int
    ) -> Embed:
        attrs = music_fetcher.get_musics(url)
        sound_queue = self.queue.setdefault(guild_id, deque())
        sound_queue.extend(attrs.music_list)
        attrs.queue_count = len(sound_queue)
        return get_add_embed(attrs)

    async def start_music(self, guild_id: int,text_channel_id:int) -> None:
        task = self._player_tasks.get(guild_id)
        if task is None or task.done():
            self._player_tasks[guild_id] = asyncio.create_task(
                self._queue_loop(guild_id, text_channel_id)
            )

    async def play_music_to_chanel(self,url:str,voice_channel_id:int,guild_id:int,text_channel_id:int) -> Embed:
        await self.core.check_and_connect(channel_id=voice_channel_id,guild_id=guild_id,force=True)
        embed = await self.add_music(url=url,guild_id=guild_id)
        await self.start_music(guild_id,text_channel_id)
        return embed


    async def _queue_loop(
        self, guild_id: int, text_channel_id: int
    ) -> None:
        queue = self.queue.get(guild_id)
        finish_event = self._track_finished_events.setdefault(
            guild_id, asyncio.Event()
        )

        while queue and len(queue) > 0:
            connection = await self.core.get_connection(guild_id)
            if not connection.connected:
                logger.info("[MusicPlayer] Connection reset. Queue stopped...")
                break
            await self._get_pause_event(guild_id).wait()
            item = queue.popleft()
            item = item.music
            print(item)
            finish_event.clear()

            # Если item уже содержит MusicAttributes или URL:
            m_attr = (
                item
                if isinstance(item, MusicAttributes)
                else music_fetcher.get_music_by_url(item.url)
            )
            logger.info(f"[MusicPlayer] Play track {m_attr.music.name}")

            async def _on_ended_handler():
                loop = asyncio.get_event_loop()
                if not finish_event.is_set():
                    loop.call_soon_threadsafe(finish_event.set)

            try:
                # 1. Сигнал: Трек НАЧАЛСЯ
                await self._notify_track_change(
                    guild_id, text_channel_id, m_attr
                )

                # 2. Воспроизведение
                await self.core.play_sound(
                    url=m_attr.music.track_url,
                    guild_id=guild_id,
                    on_ended=_on_ended_handler,
                )

                # 3. Ожидание завершения
                await finish_event.wait()

            except (PlayingException, Exception) as e:
                logger.exception(f"[MusicPlayer] Ошибка при проигрывании трека в {guild_id}: {e}")

            finally:
                # 4. Сигнал: Трек ЗАВЕРШИЛСЯ
                await self._notify_track_end(
                    guild_id, text_channel_id, m_attr
                )

        self._player_tasks.pop(guild_id, None)
        self._track_finished_events.pop(guild_id, None)