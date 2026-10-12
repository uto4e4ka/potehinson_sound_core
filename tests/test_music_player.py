import asyncio

import pytest

from potehinson_sound_core.exceptions import PlayingException
from potehinson_sound_core.music.player.player import MusicPlayer
from potehinson_sound_core.music.player.queue import QueueStreamProvider
from potehinson_sound_core.music.player.radio import RadioStreamProvider
from tests.conftest import GUILD, TEXT, VOICE, track

pytestmark = pytest.mark.usefixtures("fast_sleep")


@pytest.fixture
def player(core) -> MusicPlayer:
    return MusicPlayer(core)


async def queue_of(player, fetcher, *names) -> QueueStreamProvider:
    provider = player.get_or_create_provider(GUILD, QueueStreamProvider, music_fetcher=fetcher)
    await provider.add_music("list:" + ",".join(names))
    return provider


async def wait_finished(player, timeout=2):
    task = player._player_tasks.get(GUILD)
    if task:
        await asyncio.wait_for(asyncio.shield(task), timeout)


async def wait_until(condition, timeout=2):
    async def poll():
        while not condition():
            await asyncio.sleep(0.001)
    await asyncio.wait_for(poll(), timeout)


def played_names(discord_bot):
    return [url.removeprefix("https://cdn/").removesuffix(".mp3") for url in discord_bot.played]


class FakeRadio:
    def __init__(self):
        self.n = 0

    async def track(self):
        self.n += 1
        return track(f"wave{self.n}") if self.n <= 2 else None

    async def skip(self):
        return await self.track()


def test_provider_is_reused_for_same_type(player, fetcher):
    first = player.get_or_create_provider(GUILD, QueueStreamProvider, music_fetcher=fetcher)

    assert player.get_or_create_provider(GUILD, QueueStreamProvider, music_fetcher=fetcher) is first
    assert player.get_or_create_provider(GUILD + 1, QueueStreamProvider, music_fetcher=fetcher) is not first


def test_cannot_switch_provider_type_while_active(player, fetcher):
    player.set_provider(GUILD, RadioStreamProvider(FakeRadio()))

    with pytest.raises(PlayingException):
        player.get_or_create_provider(GUILD, QueueStreamProvider, music_fetcher=fetcher)


def test_remove_missing_provider_is_safe(player):
    player.remove_provider(GUILD)


async def test_plays_whole_queue_and_cleans_up(player, fetcher, discord_bot):
    events = []

    async def on_change(guild_id, text_channel_id, item):
        events.append(("start", item.music.name, text_channel_id))

    async def on_end(guild_id, text_channel_id, item):
        events.append(("end", item.music.name))

    player.on_track_change(on_change)
    player.on_track_end(on_end)
    await queue_of(player, fetcher, "a", "b")

    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_finished(player)

    assert discord_bot.connected_channel == VOICE
    assert played_names(discord_bot) == ["a", "b"]
    assert events == [("start", "a", TEXT), ("end", "a"), ("start", "b", TEXT), ("end", "b")]
    assert GUILD not in player.providers
    assert GUILD not in player._player_tasks


async def test_failing_listener_does_not_stop_playback(player, fetcher, discord_bot):
    async def broken(*args):
        raise RuntimeError("listener")

    player.on_track_change(broken)
    player.on_track_end(broken)
    await queue_of(player, fetcher, "a", "b")

    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_finished(player)

    assert played_names(discord_bot) == ["a", "b"]


async def test_play_error_skips_to_next_track(player, fetcher, discord_bot):
    discord_bot.failing_sounds = {"https://cdn/b.mp3"}
    await queue_of(player, fetcher, "a", "b", "c")

    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_finished(player)

    assert played_names(discord_bot) == ["a", "c"]


async def test_skip_and_previous(player, fetcher, discord_bot):
    discord_bot.auto_end = False
    await queue_of(player, fetcher, "a", "b", "c")
    await player.add_to_channel_player(VOICE, GUILD, TEXT)

    await wait_until(lambda: discord_bot.current_track)
    assert await player.skip_track(GUILD)            # a -> b
    await wait_until(lambda: len(discord_bot.played) == 2 and discord_bot.current_track)
    assert await player.previous_track(GUILD)        # b -> a
    await wait_until(lambda: len(discord_bot.played) == 3 and discord_bot.current_track)

    assert played_names(discord_bot) == ["a", "b", "a"]
    assert discord_bot.controls == ["STOP", "STOP"]
    await player.stop_player(GUILD)


async def test_previous_on_first_track(player, fetcher, discord_bot):
    discord_bot.auto_end = False
    await queue_of(player, fetcher, "a", "b")
    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_until(lambda: discord_bot.current_track)

    with pytest.raises(IndexError, match="первый трек"):
        await player.previous_track(GUILD)

    await player.stop_player(GUILD)


async def test_previous_not_supported_for_radio(player, discord_bot):
    discord_bot.auto_end = False
    player.set_provider(GUILD, RadioStreamProvider(FakeRadio()))
    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_until(lambda: discord_bot.current_track)

    with pytest.raises(IndexError, match="не поддерживает"):
        await player.previous_track(GUILD)

    await player.stop_player(GUILD)


async def test_radio_plays_until_exhausted(player, discord_bot):
    player.set_provider(GUILD, RadioStreamProvider(FakeRadio()))

    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_finished(player)

    assert played_names(discord_bot) == ["wave1", "wave2"]


async def test_skip_and_previous_without_player(player):
    assert await player.skip_track(GUILD) is False
    assert await player.previous_track(GUILD) is False


async def test_pause_and_resume(player, fetcher, discord_bot):
    discord_bot.auto_end = False
    await queue_of(player, fetcher, "a")
    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_until(lambda: discord_bot.current_track)

    assert await player.pause_track(GUILD) is True
    assert await player.pause_track(GUILD) is False
    assert await player.resume_track(GUILD, VOICE) is True
    assert await player.resume_track(GUILD, VOICE) is False
    await discord_bot.bus.settle()

    assert discord_bot.controls == ["PAUSE", "RESUME"]
    await player.stop_player(GUILD)


async def test_stop_player_cleans_everything(player, fetcher, discord_bot):
    discord_bot.auto_end = False
    await queue_of(player, fetcher, "a", "b")
    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_until(lambda: discord_bot.current_track)

    await player.stop_player(GUILD)
    await player.stop_player(GUILD)   # повторная остановка не падает

    assert "STOP" in discord_bot.controls
    assert GUILD not in player.providers
    assert GUILD not in player._player_tasks


async def test_waits_while_disconnected(player, fetcher, discord_bot):
    discord_bot.auto_end = False
    await queue_of(player, fetcher, "a")
    await player.start_player(GUILD, TEXT)   # бот не в голосовом канале

    await asyncio.sleep(0.05)
    assert discord_bot.played == []

    discord_bot.connected_channel = VOICE
    await player.resume_track(GUILD, VOICE)
    await wait_until(lambda: discord_bot.played)

    await player.stop_player(GUILD)
