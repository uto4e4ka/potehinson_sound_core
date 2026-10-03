import asyncio
from typing import Awaitable, Callable, Dict, List, Optional

from loguru import logger
from potehinsonnet.net_models.discord_models import Embed

from exeptions.playing_execptions import PlayingException
from integrations.music.music_models import MusicAttributes
from integrations.music.player.providers.base_stream_provider import BaseStreamProvider
from potehinson_sound_core.core import Core

TrackChangeCallback = Callable[[int, int, MusicAttributes], Awaitable[None]]
TrackEndCallback = Callable[[int, int, MusicAttributes], Awaitable[None]]


class MusicPlayer:

    def __init__(self, core: Core) -> None:
        self.core = core
        self._player_tasks: Dict[int, asyncio.Task] = {}
        self._track_finished_events: Dict[int, asyncio.Event] = {}

        self._track_change_listeners: List[TrackChangeCallback] = []
        self._track_end_listeners: List[TrackEndCallback] = []
        self._pause_events: Dict[int, asyncio.Event] = {}

        self._skipped_flags: Dict[int, bool] = {}
        self._previous_flags: Dict[int, bool] = {}
        self.providers: Dict[int, BaseStreamProvider] = {}

    def set_provider(self, guild_id: int, provider: BaseStreamProvider) -> None:
        self.providers[guild_id] = provider

    def _get_pause_event(self, guild_id: int) -> asyncio.Event:
        if guild_id not in self._pause_events:
            event = asyncio.Event()
            event.set()
            self._pause_events[guild_id] = event
        return self._pause_events[guild_id]

    async def pause_track(self, guild_id: int) -> bool:
        pause_event = self._get_pause_event(guild_id)
        if pause_event.is_set():
            pause_event.clear()
            try:
                await self.core.pause_sound(guild_id=guild_id)
            except Exception as e:
                logger.error(f"[MusicPlayer] Ошибка при паузе в core: {e}")
            return True
        return False

    async def resume_track(self, guild_id: int,voice_channel_id:int) -> bool:

        pause_event = self._get_pause_event(guild_id)
        if not pause_event.is_set():
            await self.core.check_and_connect(
                channel_id=voice_channel_id, guild_id=guild_id, force=False
            )
            pause_event.set()
            try:
                await self.core.resume_sound(guild_id=guild_id)
            except Exception as e:
                logger.error(f"[MusicPlayer] Ошибка при возобновлении в core: {e}")
            return True
        return False

    async def skip_track(self, guild_id: int) -> bool:
        task = self._player_tasks.get(guild_id)
        if not task or task.done():
            return False

        self._skipped_flags[guild_id] = True

        pause_event = self._get_pause_event(guild_id)
        if not pause_event.is_set():
            pause_event.set()

        try:
            await self.core.stop_sound(guild_id=guild_id)
        except Exception as e:
            logger.error(f"[MusicPlayer] Ошибка при остановке звука в core: {e}")

        logger.debug(f"[MusicPlayer] Трек принудительно пропущен для гильдии {guild_id}")
        return True

    async def previous_track(self, guild_id: int) -> bool:
        task = self._player_tasks.get(guild_id)
        if not task or task.done():
            return False

        provider = self.providers.get(guild_id)
        if not provider:
            return False

        is_implemented = (
                type(provider).prev_track is not BaseStreamProvider.prev_track
                or type(provider).prev_track is not BaseStreamProvider.prev_track
        )

        if not is_implemented:
            raise IndexError("❌ Данный тип воспроизведения не поддерживает перемотки назад.")

        if not provider.has_previous():
            raise IndexError("✅ Это уже самый первый трек")

        self._previous_flags[guild_id] = True

        pause_event = self._get_pause_event(guild_id)
        if not pause_event.is_set():
            pause_event.set()

        try:
            await self.core.stop_sound(guild_id=guild_id)
        except Exception as e:
            logger.error(f"[MusicPlayer] Ошибка при остановке звука в core: {e}")

        logger.debug(f"[MusicPlayer] Откат на предыдущий трек для гильдии {guild_id}")
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

    async def start_player(self, guild_id: int, text_channel_id: int) -> None:
        task = self._player_tasks.get(guild_id)
        if task is None or task.done():
            self._player_tasks[guild_id] = asyncio.create_task(
                self._queue_loop(guild_id, text_channel_id)
            )

    async def stop_player(self, guild_id: int) -> None:
        task = self._player_tasks.get(guild_id)
        if task is None or task.done():
            return
        task.cancel()
        try:
            await self.core.stop_sound(guild_id=guild_id)
        except Exception as e:
            logger.error(
                f"[MusicPlayer] Ошибка при остановке звука в core: {e}"
            )
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def add_to_channel_player(
            self, voice_channel_id: int, guild_id: int, text_channel_id: int
    ) -> None:
        await self.core.check_and_connect(
            channel_id=voice_channel_id, guild_id=guild_id, force=True
        )
        await self.start_player(guild_id, text_channel_id)

    async def _queue_loop(self, guild_id: int, text_channel_id: int) -> None:
        finish_event = self._track_finished_events.setdefault(
            guild_id, asyncio.Event()
        )
        pause_event = self._get_pause_event(guild_id)

        try:
            while True:
                connection = await self.core.get_connection(guild_id)
                if not connection.connected:
                    logger.warning(
                        f"[MusicPlayer] Соединение потеряно для guild={guild_id}. "
                        "Плеер автоматически поставлен на паузу."
                    )
                    pause_event.clear()
                await pause_event.wait()

                provider = self.providers.get(guild_id)
                if not provider:
                    logger.warning(f"[MusicPlayer] Провайдер не найден для guild={guild_id}. Ждем...")
                    await asyncio.sleep(2)
                    continue

                if self._previous_flags.get(guild_id, False):
                    try:
                        m_attr = await provider.prev_track()
                    except Exception:
                        self._previous_flags[guild_id] = False
                        continue
                elif self._skipped_flags.get(guild_id, False):
                    try:
                        m_attr = await provider.skip_track()
                    except Exception:
                        self._skipped_flags[guild_id] = False
                        continue
                else:
                    m_attr = await provider.next_track()

                self._skipped_flags[guild_id] = False
                self._previous_flags[guild_id] = False

                if m_attr is None:
                    logger.info(f"[MusicPlayer] В очереди нет треков для guild={guild_id}. Ожидание...")
                    await asyncio.sleep(2)
                    break

                logger.info(f"[MusicPlayer] Play track '{m_attr.music.name}' (guild={guild_id})")
                finish_event.clear()

                async def _on_ended_handler():
                    loop = asyncio.get_running_loop()
                    if not finish_event.is_set():
                        loop.call_soon_threadsafe(finish_event.set)

                try:
                    await self._notify_track_change(guild_id, text_channel_id, m_attr)

                    await self.core.play_sound(
                        url=m_attr.music.track_url,
                        guild_id=guild_id,
                        on_ended=_on_ended_handler,
                    )

                    await finish_event.wait()

                except (PlayingException, Exception) as e:
                    logger.exception(f"[MusicPlayer] Ошибка проигрывания в guild={guild_id}: {e}")
                    await asyncio.sleep(1)
                finally:
                    await self._notify_track_end(guild_id, text_channel_id, m_attr)

        finally:
            self._player_tasks.pop(guild_id, None)
            self._track_finished_events.pop(guild_id, None)
            self._skipped_flags.pop(guild_id, None)
            self._previous_flags.pop(guild_id, None)
            self._pause_events.pop(guild_id, None)
            logger.info(f"[MusicPlayer] Таска плеера завершена для guild={guild_id}")