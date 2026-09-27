import asyncio
from asyncio import Event
from typing import Awaitable, Callable

from loguru import logger

from integrations.music.music_models import MusicAttributes
from integrations.music.radios.radio import BaseRadio
from potehinson_sound_core.core import Core
from potehinson_sound_core.utils import retry
from potehinsonnet.net_models.discord_models import Embed

TrackChangeCallback = Callable[
    [int, int, MusicAttributes],
    Awaitable[None],
]


class RadioClient:
    def __init__(self, core: Core):
        self.core = core
        self._track_change_listeners: list[TrackChangeCallback] = []
        self._skip_events: dict[int, Event] = {}

    def add_track_change_listener(
        self,
        callback: TrackChangeCallback,
    ) -> None:
        self._track_change_listeners.append(callback)

    async def stream_to_channel(
            self,
            radio: BaseRadio,
            channel_id: int,
            guild_id: int,
            text_channel_id: int,
    ) -> Embed:
        await self.core.check_and_connect(
            channel_id=channel_id,
            guild_id=guild_id,
            force=False,
        )

        skip_queue: asyncio.Queue[None] = asyncio.Queue()
        self._skip_events[guild_id] = skip_queue

        asyncio.create_task(
            self.__stream_proces(
                radio,
                guild_id,
                text_channel_id,
                skip_queue,
            )
        )

        return Embed(title="Radio Stream")

    async def skip(self, guild_id: int) -> None:
        skip_queue = self._skip_events.get(guild_id)

        if skip_queue:
            skip_queue.put_nowait(None)

    async def __stream_proces(
            self,
            radio: BaseRadio,
            guild_id: int,
            text_channel_id: int,
            skip_queue: asyncio.Queue[None],
    ):
        music = None

        try:
            while True:
                if music is None:
                    music = await radio.track()

                logger.debug("Загружен трек: {}", music.music.name)

                for listener in self._track_change_listeners:
                    try:
                        await listener(
                            guild_id,
                            text_channel_id,
                            music,
                        )
                    except Exception as e:
                        logger.error(
                            "Ошибка в listener смены трека: {}",
                            e,
                        )

                finished = asyncio.Event()

                async def on_track_end():
                        finished.set()

                await self.core.play_sound(
                    url=music.music.track_url,
                    guild_id=guild_id,
                    on_ended=on_track_end,
                )

                track_task = asyncio.create_task(finished.wait())
                skip_task = asyncio.create_task(skip_queue.get())

                done, pending = await asyncio.wait(
                    {track_task, skip_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()

                await asyncio.gather(
                    *pending,
                    return_exceptions=True,
                )

                if skip_task in done:
                    logger.debug("Skip guild={}", guild_id)
                    await self.core.stop_sound(guild_id)
                    music = await radio.skip()
                    continue

                music = None

        finally:
            self._skip_events.pop(guild_id, None)