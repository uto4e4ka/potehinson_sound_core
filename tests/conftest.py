import asyncio
import itertools
from dataclasses import dataclass, field

import pytest
from potehinsonnet.net_models.discord_models import Channel, ExecutedCommand, ExecutedComponent, Guild, User

from potehinson_sound_core.music.embeds import AddingType, MusicAddMessage
from potehinson_sound_core.music.models import (
    AudioQuality,
    Music,
    MusicAttributes,
    MusicAuthor,
    MusicQueueItem,
    MusicSource,
)
from potehinson_sound_core.core import Core
from potehinsonnet.testing import FakeNats

GUILD = 10
VOICE = 20
TEXT = 30

_real_sleep = asyncio.sleep


@pytest.fixture(autouse=True)
def no_cover_downloads(monkeypatch):
    """Карточка трека скачивает обложку ради цвета — в тестах без сети."""

    async def no_color(url):
        return None

    monkeypatch.setattr("potehinson_sound_core.music.components.extract_dominant_color", no_color)
    monkeypatch.setattr("potehinson_sound_core.music.track_messages.extract_dominant_color", no_color)


@pytest.fixture
def fast_sleep(monkeypatch):
    """Плеер ждёт по 1-2 секунды между попытками — в тестах это лишнее."""

    async def sleep(delay, *args, **kwargs):
        await _real_sleep(min(delay, 0.001), *args, **kwargs)

    monkeypatch.setattr(asyncio, "sleep", sleep)


@pytest.fixture
def bus() -> FakeNats:
    return FakeNats()


@pytest.fixture
def nats(bus):
    return bus.client()


@dataclass
class FakeDiscordBot:
    """Отвечает на запросы sound core так, как это делает DiscordPotehaBot."""

    bus: FakeNats
    nats: object
    connected_channel: int | None = None
    auto_end: bool = True
    play_error: str | None = None
    failing_sounds: set[str] = field(default_factory=set)
    played: list[str] = field(default_factory=list)
    controls: list[str] = field(default_factory=list)
    sent: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    edited: list[dict] = field(default_factory=list)
    current_track: str | None = None
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1000))

    async def start(self):
        subs = {
            "discord.interaction.channel.voice.connection.status": self.status,
            "discord.interaction.channel.voice.actions.connect": self.connect,
            "discord.interaction.channel.voice.actions.play_sound": self.play,
            "discord.interaction.channel.voice.actions.control": self.control,
            "discord.message.send": self.send,
            "discord.message.remove": self.remove,
            "discord.message.edit": self.edit,
        }
        for subject, handler in subs.items():
            await self.nats.subscribe(subject, handler)

    def _status(self, guild_id: int) -> dict:
        connected = self.connected_channel is not None
        return {
            "channel": {"id": self.connected_channel, "name": "voice"} if connected else None,
            "guild": {"id": guild_id, "name": "guild"},
            "connected": connected,
            "playing": self.current_track is not None,
            "paused": False,
        }

    async def status(self, body):
        return self._status(int(body["guild_id"]))

    async def connect(self, body):
        if body["interaction_type"] == "disconnect":
            self.connected_channel = None
        else:
            self.connected_channel = body["channel"]["id"]
        return self._status(body["guild"]["id"])

    async def play(self, body):
        if self.play_error or body["sound"] in self.failing_sounds:
            return {"success": False, "message": self.play_error or "битый трек"}
        self.played.append(body["sound"])
        self.current_track = body["track_id"]
        if self.auto_end:
            asyncio.get_running_loop().call_soon(lambda: asyncio.ensure_future(self.end_current()))
        return {"success": True}

    async def end_current(self, success: bool = True):
        track_id, self.current_track = self.current_track, None
        if track_id:
            await self.nats.publish(
                f"discord.interaction.channel.voice.events.sound_ended.{track_id}",
                {"guild_id": GUILD, "track_id": track_id, "success": success, "error": None},
            )

    async def control(self, body):
        self.controls.append(body["action"])
        if body["action"] == "STOP":
            # discord.py вызывает after() при остановке — бот сообщает об окончании трека
            await self.end_current()

    async def send(self, body):
        self.sent.append(body)
        return {"channel_id": body["channel_id"], "message_id": next(self._ids)}

    async def remove(self, body):
        self.removed.append(body)

    async def edit(self, body):
        self.edited.append(body)
        return {"channel_id": body["message"]["channel_id"], "message_id": body["message_id"]}


@pytest.fixture
async def discord_bot(bus, nats) -> FakeDiscordBot:
    bot = FakeDiscordBot(bus=bus, nats=nats)
    await bot.start()
    return bot


@pytest.fixture
def core(nats) -> Core:
    return Core(nats)


def track(name: str, icon: str = "https://img/cover.png") -> MusicAttributes:
    return MusicAttributes(
        source=MusicSource.YANDEX_MUSIC,
        duration=125,
        music=Music(name=name, url=f"https://music/{name}", track_url=f"https://cdn/{name}.mp3", icon_url=icon, id=name),
        author=MusicAuthor(name="Artist"),
        quality=AudioQuality.HIGH,
    )


class FakeFetcher:
    """Вместо MusicFetcher: ссылка вида "list:a,b,c" добавляет треки a, b, c."""

    def __init__(self, broken: set[str] = frozenset()):
        self.broken = set(broken)
        self.fetched: list[str] = []

    async def get_musics(self, url: str) -> MusicAddMessage:
        names = url.removeprefix("list:").split(",")
        return MusicAddMessage(
            add_type=AddingType.PLAYLIST,
            source=MusicSource.YANDEX_MUSIC,
            name=url,
            count=len(names),
            music_list=[MusicQueueItem(music=Music(name=n, url=n)) for n in names],
        )

    async def get_music_by_url(self, url: str) -> MusicAttributes:
        self.fetched.append(url)
        if url in self.broken:
            raise FileNotFoundError(url)
        return track(url)


@pytest.fixture
def fetcher() -> FakeFetcher:
    return FakeFetcher()


def executed(*, in_voice: bool = True, args: dict | None = None, user_id: int = 1, entity_id: str = "E1") -> ExecutedCommand:
    return ExecutedCommand(
        service="potehinson_sound_core",
        tag="t",
        entity_id=entity_id,
        user=User(id=user_id, name="user", voice_channel=Channel(id=VOICE, name="voice") if in_voice else None),
        guild=Guild(id=GUILD, name="guild"),
        channel=Channel(id=TEXT, name="text"),
        args=[{"name": k, "value": v, "type": "str"} for k, v in (args or {}).items()],
    )


def clicked(custom_id: str, context: dict | None = None, in_voice: bool = False) -> ExecutedComponent:
    return ExecutedComponent(
        id=custom_id,
        user=User(id=1, name="user", voice_channel=Channel(id=VOICE, name="voice") if in_voice else None),
        guild=Guild(id=GUILD, name="guild"),
        channel=Channel(id=TEXT, name="text"),
        task_id="T1",
        context=context,
    )
