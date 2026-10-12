"""Приветствия: репозиторий, реакция на вход в канал и команды /greeting."""
import asyncio

import pytest
from potehinsonnet.net_models.discord_models import Channel, Guild, User, VoiceChannelUserConnectionEvent

from commands.greeteng_commands import GreetingCommands
from potehinson_sound_core.user_interaction import UserInteraction
from scenaries.greeting_repository import GreetingRepository, GreetingScenario
from tests.conftest import GUILD, VOICE, executed


@pytest.fixture
def repo(tmp_path) -> GreetingRepository:
    return GreetingRepository(json_path=str(tmp_path / "data" / "greeting.json"), default_sound_url="sounds/default.mp3")


def test_default_greeting_when_not_configured(repo):
    greeting = repo.get_greeting(GUILD, 1)

    assert greeting.sound_url == "sounds/default.mp3"
    assert not greeting.disabled


def test_set_get_remove_greeting(repo):
    repo.set_greeting(GreetingScenario(user_id=1, guild_id=GUILD, sound_url="https://s/1.mp3"))

    assert repo.get_greeting(GUILD, 1).sound_url == "https://s/1.mp3"
    assert repo.get_greeting(GUILD + 1, 1).sound_url == "sounds/default.mp3"
    assert repo.remove_greeting(GUILD, 1).sound_url == "https://s/1.mp3"
    assert repo.get_greeting(GUILD, 1).sound_url == "sounds/default.mp3"
    with pytest.raises(KeyError):
        repo.remove_greeting(GUILD, 1)


def test_corrupted_file_is_ignored(repo):
    repo.json_path.parent.mkdir(parents=True)
    repo.json_path.write_text("{oops", encoding="utf-8")

    assert repo.get_greeting(GUILD, 1).sound_url == "sounds/default.mp3"


async def test_greeting_commands(repo):
    commands = GreetingCommands(repo)

    added = await commands.handle_add(executed(args={"user": "42", "url": "https://s/hi.mp3"}))
    removed = await commands.handle_remove(executed(args={"user": "42"}))
    missing = await commands.handle_remove(executed(args={"user": "42"}))

    assert "<@42>" in added.message and added.is_final
    assert "Удалено" in removed.message
    assert "не найдено" in missing.message


def join_event(action="connected", is_bot=False, user_id=1) -> dict:
    return VoiceChannelUserConnectionEvent(
        user=User(id=user_id, name="vasya", is_bot=is_bot),
        before_channel=None if action == "connected" else Channel(id=VOICE, name="voice"),
        after_channel=Channel(id=VOICE, name="voice") if action != "disconnected" else None,
        guild=Guild(id=GUILD, name="guild"),
        action=action,
    ).model_dump(mode="json")


@pytest.fixture
async def interaction(core, nats, repo, discord_bot):
    interaction = UserInteraction(core, nats, is_greeting=True, greeting_repository=repo)
    await interaction.start()
    yield interaction
    await interaction.stop()


async def test_user_join_plays_greeting_then_leaves(interaction, discord_bot, bus, nats):
    await nats.publish("discord.interaction.channel.voice.event.user.connection", join_event())
    await bus.settle()
    await asyncio.sleep(0.01)
    await bus.settle()

    assert discord_bot.played == ["sounds/default.mp3"]
    # после приветствия бот выходит из канала
    assert discord_bot.connected_channel is None


@pytest.mark.parametrize("event", [
    join_event(is_bot=True),
    join_event(action="disconnected"),
])
async def test_ignored_events(interaction, discord_bot, bus, nats, event):
    await nats.publish("discord.interaction.channel.voice.event.user.connection", event)
    await bus.settle()

    assert discord_bot.played == []


async def test_disabled_greeting(interaction, repo, discord_bot, bus, nats):
    repo.set_greeting(GreetingScenario(user_id=1, guild_id=GUILD, sound_url="x", disabled=True))

    await nats.publish("discord.interaction.channel.voice.event.user.connection", join_event())
    await bus.settle()

    assert discord_bot.played == []


async def test_no_greeting_while_music_plays(interaction, discord_bot, bus, nats):
    discord_bot.current_track = "music"

    await nats.publish("discord.interaction.channel.voice.event.user.connection", join_event())
    await bus.settle()

    assert discord_bot.played == []


async def test_greetings_turned_off(core, nats, repo, discord_bot, bus):
    async with UserInteraction(core, nats, is_greeting=False, greeting_repository=repo):
        await nats.publish("discord.interaction.channel.voice.event.user.connection", join_event())
        await bus.settle()

    assert discord_bot.played == []
