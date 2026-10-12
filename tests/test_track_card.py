"""Карточка "Сейчас играет" обновляется, когда меняется состояние плеера."""
import pytest
from potehinsonnet.discord_provider import DiscordProvider

from potehinson_sound_core.exceptions import PlayingException
from potehinson_sound_core.music.buttons import ButtonControl
from potehinson_sound_core.music.commands import MusicCommands
from potehinson_sound_core.music.player.player import MusicPlayer, PlayerState
from potehinson_sound_core.music.player.queue import QueueStreamProvider
from potehinson_sound_core.music.track_messages import TrackMessageService
from tests.conftest import GUILD, TEXT, VOICE, clicked, executed, track
from tests.test_music_player import wait_until

pytestmark = pytest.mark.usefixtures("fast_sleep")


@pytest.fixture
def player(core) -> MusicPlayer:
    return MusicPlayer(core)


@pytest.fixture
def card_service(nats, player) -> TrackMessageService:
    """Карточка подключена к плееру так же, как в create_plugin()."""
    service = TrackMessageService(DiscordProvider(nats), player)
    player.on_track_change(service.on_music_change)
    player.on_track_end(service.on_music_end)
    player.on_state_change(service.on_state_change)
    return service


@pytest.fixture
def buttons(player) -> ButtonControl:
    return ButtonControl(player, yandex_repo=None)


@pytest.fixture
async def playing(player, fetcher, discord_bot):
    """Играет первый трек очереди a, b (карточка отправляется до начала воспроизведения)."""
    discord_bot.auto_end = False
    provider = player.get_or_create_provider(GUILD, QueueStreamProvider, music_fetcher=fetcher)
    await provider.add_music("list:a,b")
    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_until(lambda: discord_bot.current_track)
    yield
    await player.stop_player(GUILD)


def card_buttons(message: dict) -> dict[str, dict]:
    rows = [c for c in message["containers"][0]["components"] if "components" in c and "accessory" not in c]
    return {b["custom_id"]: b for row in rows for b in row["components"] if b.get("custom_id")}


@pytest.mark.usefixtures("card_service", "playing")
async def test_pause_button_updates_card(buttons, discord_bot, bus):
    assert card_buttons(discord_bot.sent[0])["music:pause"]["label"] == "⏸"

    await buttons.pause(clicked("music:pause"))
    await bus.settle()

    [edit] = discord_bot.edited
    assert edit["message_id"] == 1000          # правится та же карточка
    assert len(discord_bot.sent) == 1          # новое сообщение не отправляется
    assert card_buttons(edit["message"])["music:pause"]["label"] == "▶️"

    await buttons.pause(clicked("music:pause", in_voice=True))   # та же кнопка продолжает
    await bus.settle()

    assert card_buttons(discord_bot.edited[-1]["message"])["music:pause"]["label"] == "⏸"
    assert discord_bot.controls == ["PAUSE", "RESUME"]


@pytest.mark.usefixtures("playing")
async def test_resume_from_card_requires_voice(buttons):
    await buttons.pause(clicked("music:pause"))

    with pytest.raises(PlayingException, match="голосовом канале"):
        await buttons.pause(clicked("music:pause"))


@pytest.mark.usefixtures("card_service", "playing")
async def test_shuffle_button_updates_card(buttons, discord_bot, bus):
    assert card_buttons(discord_bot.sent[0])["music:shuffle"]["label"] == "🔀"

    await buttons.shuffle(clicked("music:shuffle"))
    await bus.settle()

    assert card_buttons(discord_bot.edited[-1]["message"])["music:shuffle"]["label"] == "↔️"


@pytest.mark.usefixtures("card_service", "playing")
async def test_shuffle_command_updates_card(player, fetcher, discord_bot, bus):
    await MusicCommands(player, fetcher).shuffle(executed())
    await bus.settle()

    assert card_buttons(discord_bot.edited[-1]["message"])["music:shuffle"]["label"] == "↔️"


@pytest.mark.usefixtures("card_service", "playing")
async def test_previous_button_disabled_on_first_track(player, discord_bot):
    assert card_buttons(discord_bot.sent[0])["music:prev"]["disabled"] is True

    await player.skip_track(GUILD)
    await wait_until(lambda: len(discord_bot.sent) == 2)

    assert card_buttons(discord_bot.sent[1])["music:prev"]["disabled"] is False


@pytest.mark.usefixtures("card_service")
async def test_card_update_does_not_download_cover_again(player, fetcher, discord_bot, bus, monkeypatch):
    downloads = []

    async def color(url):
        downloads.append(url)
        return 0x123456

    monkeypatch.setattr("potehinson_sound_core.music.track_messages.extract_dominant_color", color)
    discord_bot.auto_end = False
    provider = player.get_or_create_provider(GUILD, QueueStreamProvider, music_fetcher=fetcher)
    await provider.add_music("list:a")
    await player.add_to_channel_player(VOICE, GUILD, TEXT)
    await wait_until(lambda: discord_bot.current_track)

    await player.pause_track(GUILD)
    await bus.settle()

    assert downloads == ["https://img/cover.png"]
    assert discord_bot.edited[-1]["message"]["containers"][0]["accent_color"] == 0x123456
    await player.stop_player(GUILD)


@pytest.mark.usefixtures("card_service", "playing")
async def test_card_update_error_is_swallowed(card_service, player):
    attempts = []

    async def fail(message):
        attempts.append(message.message_id)
        raise TimeoutError()

    card_service.discord_provider.update_message = fail

    await player.pause_track(GUILD)   # карточку обновить не удалось, но пауза сработала

    assert attempts == [1000]
    assert player.is_paused(GUILD)


async def test_state_change_without_card_does_nothing(card_service, player, discord_bot, bus):
    await card_service.on_state_change(PlayerState(GUILD, TEXT, track("a"), True, False, False))
    await bus.settle()

    assert discord_bot.edited == []
