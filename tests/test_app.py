"""Сборка плагина целиком (create_plugin): регистрация команд и кнопок через фейковый бот."""
import pytest

from potehinson_sound_core.app import create_plugin
from potehinson_sound_core.settings import PROJECT_ROOT, Settings
from tests.conftest import clicked, executed

EXPECTED_COMMANDS = {
    "play", "skip", "pause", "resume", "shuffle", "previous", "say",
    "add_greeting", "remove_greeting", "yandex_wave", "wave_skip",
}


@pytest.fixture
async def bot_registration(nats):
    """Бот отвечает на регистрацию плагина — иначе плагин ждёт его 10 секунд."""

    async def registration(data):
        return {"type": "bot", "name": "999", "label": "Potehinson", "author": "", "version": "0.0.1"}

    await nats.subscribe("system.info.registration.request", registration)


@pytest.fixture
async def plugin(bus, discord_bot, bot_registration, tmp_path):
    settings = Settings(greeting_enabled=True, greeting_json_path=str(tmp_path / "greeting.json"))
    plugin = create_plugin(settings, nats=bus.client())
    async with plugin:
        await bus.settle()
        yield plugin


async def test_all_commands_are_registered_with_bot(plugin, bus):
    registered = bus.messages("discord.command.register")

    assert {c["tag"] for c in registered} == EXPECTED_COMMANDS
    assert {c["service"] for c in registered} == {"potehinson_sound_core"}
    assert {c["group"] for c in registered} == {"", "greeting", "wave"}
    assert all(c["permission"].startswith("sound_core.") for c in registered)
    assert bus.messages("discord.command.sync")


async def test_slash_command_roundtrip(plugin, bus, nats):
    await nats.publish(
        "discord.command.execute.potehinson_sound_core.play",
        executed(in_voice=False, args={"url": "x"}).model_dump(mode="json"),
    )
    await bus.settle()

    [reply] = bus.messages("discord.command.reply.E1")
    assert "голосовом канале" in reply["message"] and reply["is_final"]


async def test_card_buttons_are_registered(plugin, bus, nats):
    await nats.publish("discord.component.execute", clicked("music:shuffle").model_dump(mode="json"))
    await bus.settle()

    # очереди нет — кнопка отвечает ошибкой, но отвечает
    [reply] = bus.messages("discord.component.T1.reply")
    assert reply["message"] == "Не доступно в этом режиме."


async def test_greeting_listener_is_active(plugin, bus):
    assert bus.has_subscription("discord.interaction.channel.voice.event.user.connection")


async def test_plugin_stops_cleanly(bus, discord_bot, bot_registration, tmp_path):
    plugin = create_plugin(Settings(greeting_json_path=str(tmp_path / "g.json")), nats=bus.client())

    async with plugin:
        pass

    assert not bus.has_subscription("discord.interaction.channel.voice.event.user.connection")
    assert not bus.has_subscription("discord.component.execute")
    assert not [s for s in bus.subscriptions if s.subject.startswith("discord.command.execute")]


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("GREETING", "false")
    monkeypatch.setenv("GREETING_SOUND", "sounds/hi.mp3")
    monkeypatch.setenv("NATS_URL", "nats://nats:4222")
    monkeypatch.setenv("TTS_PORT", "9000")

    settings = Settings.from_env()

    # раньше строка "false" считалась включённым приветствием
    assert settings.greeting_enabled is False
    assert settings.greeting_sound == "sounds/hi.mp3"
    assert settings.nats_url == "nats://nats:4222"
    assert settings.tts_port == 9000


@pytest.mark.parametrize("value, expected", [("true", True), ("1", True), ("YES", True), ("false", False), ("0", False), ("", False)])
def test_greeting_flag_parsing(monkeypatch, value, expected):
    monkeypatch.setenv("GREETING", value)

    assert Settings.from_env().greeting_enabled is expected


def test_defaults_without_env(monkeypatch):
    for name in ("GREETING", "GREETING_SOUND", "NATS_URL", "TTS_HOST", "TTS_PORT", "GREETING_JSON_PATH"):
        monkeypatch.delenv(name, raising=False)

    assert Settings.from_env() == Settings()


def test_greeting_data_path_does_not_depend_on_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("GREETING_JSON_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    assert Settings.from_env().greeting_json_path == str(PROJECT_ROOT / "data" / "greeting.json")
    assert (PROJECT_ROOT / "data" / "greeting.json").exists()
