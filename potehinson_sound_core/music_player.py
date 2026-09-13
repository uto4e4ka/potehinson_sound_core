import asyncio
from collections import deque
from typing import Awaitable, Callable, Dict, List

from exeptions.playing_execptions import PlayingException
from integrations.music_models import MusicAttributes, MusicQueueItem
from potehinson_sound_core import sound_classificator
from potehinson_sound_core.core import Core

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
        self, url: str, guild_id: int, text_channel_id: int, channel_id: int
    ) -> str:
        attrs = sound_classificator.get_musics(url)
        sound_queue = self.queue.setdefault(guild_id, deque())
        sound_queue.extend(attrs)

        task = self._player_tasks.get(guild_id)
        if task is None or task.done():
            self._player_tasks[guild_id] = asyncio.create_task(
                self._queue_loop(guild_id, channel_id, text_channel_id)
            )
        return f"Добавлено {len(attrs)} треков"

    async def _queue_loop(
        self, guild_id: int, channel_id: int, text_channel_id: int
    ) -> None:
        queue = self.queue.get(guild_id)
        finish_event = self._track_finished_events.setdefault(
            guild_id, asyncio.Event()
        )

        while queue and len(queue) > 0:
            item = queue.popleft()
            finish_event.clear()

            # Если item уже содержит MusicAttributes или URL:
            m_attr = (
                item
                if isinstance(item, MusicAttributes)
                else sound_classificator.get_music_by_url(item.music.url)
            )

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
                    channel_id=channel_id,
                    guild_id=guild_id,
                    on_ended=_on_ended_handler,
                )

                # 3. Ожидание завершения
                await finish_event.wait()

            except (PlayingException, Exception) as e:
                print(
                    f"[MusicPlayer] Ошибка при проигрывании трека в {guild_id}: {e}"
                )

            finally:
                # 4. Сигнал: Трек ЗАВЕРШИЛСЯ
                await self._notify_track_end(
                    guild_id, text_channel_id, m_attr
                )

        self._player_tasks.pop(guild_id, None)
        self._track_finished_events.pop(guild_id, None)