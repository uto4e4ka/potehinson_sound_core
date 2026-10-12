"""Слэш-команды музыки/TTS/волны, кнопки карточки и сообщения о треке."""
from urllib.parse import parse_qs, urlparse

import pytest

from commands.music_commands import MusicCommands
from commands.tts_commands import TTSCommands
from commands.yandex_commands import YandexRadioCommands
from control.button_control import ButtonControl
from integrations.music.music_fetcher import MusicFetcher
from integrations.music.player.music_player import MusicPlayer
from integrations.music.player.providers.queue_stream_provider import QueueStreamProvider
from integrations.music.player.providers.radio_stream_provider import RadioStreamProvider
from integrations.music.resolvers.tts.tts_resolver import TtsResolver
from integrations.music.track_message_service import TrackMessageService
from potehinsonnet.discord_provider import DiscordProvider
from tests.conftest import GUILD, TEXT, VOICE, clicked, executed, track
from tests.test_music_player import wait_finished, wait_until

pytestmark = pytest.mark.usefixtures("fast_sleep")


@pytest.fixture
def player(core) -> MusicPlayer:
    return MusicPlayer(core)


@pytest.fixture
def music(player, fetcher) -> MusicCommands:
    return MusicCommands(player, fetcher)


async def test_play_requires_voice_channel(music):
    response = await music.handle_play(executed(in_voice=False, args={"url": "list:a"}))

    assert "голосовом канале" in response.message and response.is_final


async def test_play_adds_and_starts(music, player, discord_bot):
    response = await music.handle_play(executed(args={"url": "list:a,b"}))
    await wait_finished(player)

    assert response.embeds[0].title == "list:a,b"
    assert len(discord_bot.played) == 2


async def test_play_reports_errors(music, monkeypatch, fetcher):
    async def broken(url):
        raise FileNotFoundError("Данный тип ссылок не поддерживается.")

    monkeypatch.setattr(fetcher, "get_musics", broken)

    response = await music.handle_play(executed(args={"url": "https://unknown"}))

    assert response.message == "❌ Данный тип ссылок не поддерживается." and response.is_final


async def test_simple_player_commands(music, player, discord_bot):
    discord_bot.auto_end = False
    await music.handle_play(executed(args={"url": "list:a,b"}))
    await wait_until(lambda: discord_bot.current_track)

    assert (await music.pause(executed())).message == "⏸️ Пауза"
    assert (await music.resume(executed())).message == "▶️ Возобновляем"
    assert (await music.resume(executed())).message == "Трек не на паузе"
    assert (await music.handle_skip(executed())).message == "⏭️ Пропущено"
    await wait_until(lambda: len(discord_bot.played) == 2 and discord_bot.current_track)
    assert "Возвращаемся" in (await music.handle_previous(executed())).message
    assert "включено" in (await music.shuffle(executed())).message
    assert "отключено" in (await music.shuffle(executed())).message

    await player.stop_player(GUILD)


async def test_previous_without_player(music):
    assert "Не удалось" in (await music.handle_previous(executed())).message


async def test_music_and_tts_share_queue(player, fetcher):
    music = MusicCommands(player, fetcher)
    tts = TTSCommands(fetcher, player)

    assert music.get_provider(GUILD) is tts.get_provider(GUILD)


async def test_say_escapes_text_in_url(player, discord_bot):
    tts = TTSCommands(MusicFetcher([TtsResolver()]), player)
    discord_bot.auto_end = False

    response = await tts.say(executed(args={"text": "рок & ролл #1?"}))
    await wait_until(lambda: discord_bot.played)

    assert response.message == "🗣️ Начинаю говорить"
    query = parse_qs(urlparse(discord_bot.played[0]).query)
    assert query["text"] == ["рок & ролл #1?"]
    assert query["voice"] == ["ru-RU-DmitryNeural"]
    await player.stop_player(GUILD)


async def test_say_requires_voice(player, fetcher):
    response = await TTSCommands(fetcher, player).say(executed(in_voice=False, args={"text": "hi"}))

    assert "голосовом канале" in response.message


async def test_wave_requires_voice(player, nats):
    commands = YandexRadioCommands(yandex_repo=None, registrator=None, music_player=player)

    response = await commands.handle_wave(executed(in_voice=False))

    assert "голосовой канал" in response.message


class BrokenYandex:
    async def get_async_music_client(self, user_id):
        raise ConnectionError("нет токена")


async def test_wave_reports_errors(player, bus, nats, plugin_registrator):
    commands = YandexRadioCommands(BrokenYandex(), plugin_registrator, player)

    response = await commands.handle_wave(executed())

    assert "нет токена" in response.message and response.is_final
    assert bus.messages("discord.command.reply.E1")[0]["message"] == "Запускаю волну..."


@pytest.fixture
def plugin_registrator(nats):
    from potehinsonnet.net_models.system_models import Service
    from potehinsonnet.setup.command_registrator import CommandRegistrator

    return CommandRegistrator(nats, Service(name="potehinson_sound_core", label="", author="", version=""))


@pytest.fixture
def buttons(player) -> ButtonControl:
    return ButtonControl(player, yandex_repo=BrokenYandex())


async def test_shuffle_button(buttons, player, fetcher):
    with pytest.raises(FileNotFoundError):
        await buttons.shuffle(clicked("music:shuffle"))

    provider = player.get_or_create_provider(GUILD, QueueStreamProvider, music_fetcher=fetcher)
    await provider.add_music("list:a,b")

    assert "включено" in (await buttons.shuffle(clicked("music:shuffle"))).message
    assert "отключено" in (await buttons.shuffle(clicked("music:shuffle"))).message


async def test_shuffle_button_not_available_for_radio(buttons, player):
    player.set_provider(GUILD, RadioStreamProvider(radio=None))

    with pytest.raises(FileNotFoundError):
        await buttons.shuffle(clicked("music:shuffle"))


async def test_player_buttons(buttons, player, fetcher, discord_bot):
    discord_bot.auto_end = False
    provider = player.get_or_create_provider(GUILD, QueueStreamProvider, music_fetcher=fetcher)
    await provider.add_music("list:a,b,c")
    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_until(lambda: discord_bot.current_track)

    await buttons.pause(clicked("music:pause"))
    await buttons.skip(clicked("music:skip"))
    await wait_until(lambda: len(discord_bot.played) == 2 and discord_bot.current_track)
    await buttons.prev(clicked("music:prev"))
    await wait_until(lambda: len(discord_bot.played) == 3)
    await buttons.stop(clicked("music:stop"))

    assert discord_bot.controls[0] == "PAUSE"
    assert GUILD not in player._player_tasks


async def test_wave_button_without_track(buttons):
    with pytest.raises(FileNotFoundError):
        await buttons.wave_by_track(clicked("music:wave_from_track"))


async def test_track_message_lifecycle(nats, player, discord_bot, bus):
    service = TrackMessageService(DiscordProvider(nats), player)

    await service.on_music_change(GUILD, TEXT, track("a"))
    await service.on_music_change(GUILD, TEXT, track("b"))
    await service.on_music_end(GUILD)
    await service.on_music_end(GUILD)   # повторно — ничего не удаляем
    await bus.settle()

    assert len(discord_bot.sent) == 2
    assert discord_bot.sent[0]["containers"][0]["components"][0]["accessory"]["url"] == "https://img/cover.png"
    assert [r["message_id"] for r in discord_bot.removed] == [1000, 1001]


async def test_track_message_send_error_is_swallowed(nats, player):
    service = TrackMessageService(DiscordProvider(nats), player)

    async def fail(message):
        raise TimeoutError()

    service.discord_provider.send_message = fail

    await service.on_music_change(GUILD, TEXT, track("a"))

    assert service._active_track_messages == {}
