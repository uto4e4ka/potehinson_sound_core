import asyncio
import time
from collections import deque
from typing import Awaitable, Callable, Dict, List, Optional

from potehinsonnet.net_models.discord_models import Embed

from exeptions.playing_execptions import PlayingException
from integrations.music.music_embeds import get_add_embed
from integrations.music.music_models import MusicAttributes, MusicQueueItem
from integrations.music import music_fetcher
from potehinson_sound_core.core import Core
from loguru import logger

TrackChangeCallback = Callable[[int, int, MusicAttributes], Awaitable[None]]
TrackEndCallback = Callable[[int, int, MusicAttributes], Awaitable[None]]


class MusicPlayer:

    def __init__(self, core: Core, music_fetcher: music_fetcher.MusicFetcher) -> None:
        self.queue: Dict[int, deque[MusicQueueItem]] = {}
        self.core = core
        self._player_tasks: Dict[int, asyncio.Task] = {}
        self._track_finished_events: Dict[int, asyncio.Event] = {}

        self._track_change_listeners: List[TrackChangeCallback] = []
        self._track_end_listeners: List[TrackEndCallback] = []
        self._pause_events: Dict[int, asyncio.Event] = {}

        # 1. Добавляем словарь для отслеживания флага пропуска по guild_id
        self._skipped_flags: Dict[int, bool] = {}
        self.music_fetcher = music_fetcher

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
                await self.core.pause_sound(guild_id=guild_id)
            except Exception as e:
                logger.error(f"[MusicPlayer] Ошибка при паузе в core: {e}")
            return True
        return False

    async def resume_track(self, guild_id: int) -> bool:
        """Снимает воспроизведение с паузы."""
        pause_event = self._get_pause_event(guild_id)
        if not pause_event.is_set():
            pause_event.set()  # Снимаем блокировку
            try:
                await self.core.resume_sound(guild_id=guild_id)
            except Exception as e:
                logger.error(f"[MusicPlayer] Ошибка при возобновлении в core: {e}")
            return True
        return False

    async def skip_track(self, guild_id: int) -> bool:
        """Принудительно пропускает текущий трек и переходит к следующему."""
        task = self._player_tasks.get(guild_id)

        # Если ничего не играется, пропускать нечего
        if not task or task.done():
            return False

        # 2. Помечаем, что текущий трек был именно ПРОПУЩЕН
        self._skipped_flags[guild_id] = True

        # Если плеер на паузе — снимаем паузу, чтобы цикл продолжить
        pause_event = self._get_pause_event(guild_id)
        if not pause_event.is_set():
            pause_event.set()

        # Останавливаем воспроизведение звука в ядре
        try:
            await self.core.stop_sound(guild_id=guild_id)
        except Exception as e:
            logger.error(f"[MusicPlayer] Ошибка при остановке звука в core: {e}")

        logger.debug(f"[MusicPlayer] Трек принудительно пропущен для гильдии {guild_id}")
        return True

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
                logger.error(f"[MusicPlayer] Ошибка в listener (start): {e}")

    async def _notify_track_end(
            self, guild_id: int, text_channel_id: int, item: MusicAttributes
    ):
        for listener in self._track_end_listeners:
            try:
                await listener(guild_id, text_channel_id, item)
            except Exception as e:
                logger.error(f"[MusicPlayer] Ошибка в listener (end): {e}")

    async def add_music(
            self, url: str, guild_id: int
    ) -> Embed:
        attrs = self.music_fetcher.get_musics(url)
        sound_queue = self.queue.setdefault(guild_id, deque())
        sound_queue.extend(attrs.music_list)
        attrs.queue_count = len(sound_queue)
        return get_add_embed(attrs)

    async def start_music(self, guild_id: int, text_channel_id: int) -> None:
        task = self._player_tasks.get(guild_id)
        if task is None or task.done():
            self._player_tasks[guild_id] = asyncio.create_task(
                self._queue_loop(guild_id, text_channel_id)
            )

    async def play_music_to_chanel(
            self, url: str, voice_channel_id: int, guild_id: int, text_channel_id: int
    ) -> Embed:
        await self.core.check_and_connect(
            channel_id=voice_channel_id, guild_id=guild_id, force=True
        )
        embed = await self.add_music(url=url, guild_id=guild_id)
        await self.start_music(guild_id, text_channel_id)
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
            finish_event.clear()





            # Сбрасываем флаг пропуска перед началом нового трека
            self._skipped_flags[guild_id] = False

            # Если item уже содержит MusicAttributes или URL:
            m_attr: MusicAttributes = (
                item
                if isinstance(item, MusicAttributes)
                else self.music_fetcher.get_music_by_url(item.url)
            )

            # ЕЕСЛИ В ИСХОДНОМ ЭЛЕМЕНТЕ ОЧЕРЕДИ БЫЛ КОЛБЭК — ПЕРЕНОСИМ ЕГО:
            if item.feedback_callback and not m_attr.music.feedback_callback:
                m_attr.music.feedback_callback = item.feedback_callback

            logger.info(f"[MusicPlayer] Play track {m_attr.music.name}")

            async def _on_ended_handler():
                loop = asyncio.get_running_loop()
                if not finish_event.is_set():
                    loop.call_soon_threadsafe(finish_event.set)

            start_time = time.time()

            try:
                # 3. ОТПРАВКА СИГНАЛА "START" В ЯНДЕКС / ИСТОЧНИК
                print("try send")
                await m_attr.music.send_feedback("start", played_seconds=0.0)

                # Уведомляем локальных слушателей приложения
                await self._notify_track_change(
                    guild_id, text_channel_id, m_attr
                )

                # Воспроизведение
                await self.core.play_sound(
                    url=m_attr.music.track_url,
                    guild_id=guild_id,
                    on_ended=_on_ended_handler,
                )

                # Ожидание завершения
                await finish_event.wait()

            except (PlayingException, Exception) as e:
                logger.exception(f"[MusicPlayer] Ошибка при проигрывании трека в {guild_id}: {e}")

            finally:
                # Сколько секунд проиграл трек на самом деле
                played_seconds = time.time() - start_time

                # 4. ПРОВЕРЯЕМ: ПРОПУЩЕН ИЛИ ДОИГРАЛ ДО КОНЦА?
                is_skipped = self._skipped_flags.get(guild_id, False)
                feedback_event = "skip" if is_skipped else "finish"

                # Отправляем коллбэк в Яндекс
                await m_attr.music.send_feedback(feedback_event, played_seconds=played_seconds)

                # Уведомляем локальных слушателей приложения
                await self._notify_track_end(
                    guild_id, text_channel_id, m_attr
                )

        self._player_tasks.pop(guild_id, None)
        self._track_finished_events.pop(guild_id, None)
        self._skipped_flags.pop(guild_id, None)