import asyncio

import pytest
from potehinsonnet.net_models.discord_models import InteractionType

from potehinson_sound_core.exceptions import BotBusyException, PlayingException
from tests.conftest import GUILD, VOICE


async def test_check_and_connect_connects_when_idle(core, discord_bot):
    status = await core.check_and_connect(VOICE, GUILD, force=False)

    assert status.connected and status.channel.id == VOICE


async def test_check_and_connect_keeps_same_channel(core, discord_bot):
    discord_bot.connected_channel = VOICE

    status = await core.check_and_connect(VOICE, GUILD, force=False)

    assert status.channel.id == VOICE


async def test_check_and_connect_busy_in_other_channel(core, discord_bot):
    discord_bot.connected_channel = 999

    with pytest.raises(BotBusyException):
        await core.check_and_connect(VOICE, GUILD, force=False)

    status = await core.check_and_connect(VOICE, GUILD, force=True)
    assert status.channel.id == VOICE


async def test_disconnect(core, discord_bot):
    discord_bot.connected_channel = VOICE

    status = await core.connect(VOICE, GUILD, InteractionType.DISCONNECT)

    assert not status.connected


async def test_play_sound_calls_on_ended_once_and_unsubscribes(core, discord_bot, bus):
    ended = asyncio.Event()
    calls = []

    async def on_ended():
        calls.append(1)
        ended.set()

    await core.play_sound("https://cdn/a.mp3", GUILD, on_ended)
    await asyncio.wait_for(ended.wait(), 1)
    await bus.settle()

    assert discord_bot.played == ["https://cdn/a.mp3"]
    assert calls == [1]
    assert not [s for s in bus.subscriptions if "sound_ended" in s.subject]


async def test_track_that_ends_instantly_is_not_lost(core, nats):
    # Раньше подписка на sound_ended создавалась после запуска — короткий звук мог закончиться раньше
    ended = asyncio.Event()

    async def status(body):
        return {"channel": None, "guild": None, "connected": True}

    async def play_and_end_immediately(body):
        await nats.publish(f"discord.interaction.channel.voice.events.sound_ended.{body['track_id']}", {})
        return {"success": True}

    await nats.subscribe("discord.interaction.channel.voice.connection.status", status)
    await nats.subscribe("discord.interaction.channel.voice.actions.play_sound", play_and_end_immediately)

    async def on_ended():
        ended.set()

    await core.play_sound("https://cdn/short.mp3", GUILD, on_ended)

    await asyncio.wait_for(ended.wait(), 1)


async def test_play_failure_raises_and_cleans_up(core, discord_bot, bus):
    discord_bot.play_error = "File not found"

    async def on_ended():
        raise AssertionError("не должен вызываться")

    with pytest.raises(PlayingException, match="File not found"):
        await core.play_sound("missing.mp3", GUILD, on_ended)

    assert not [s for s in bus.subscriptions if "sound_ended" in s.subject]


async def test_controls_are_published(core, discord_bot, bus):
    await core.pause_sound(GUILD)
    await core.resume_sound(GUILD)
    await core.stop_sound(GUILD)
    await bus.settle()

    assert discord_bot.controls == ["PAUSE", "RESUME", "STOP"]
