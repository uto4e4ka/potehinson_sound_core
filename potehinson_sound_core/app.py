"""Сборка плагина: все объекты создаются здесь, в одном месте и в явном порядке."""
import os
from dataclasses import dataclass

from potehinsonnet import Plugin
from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.system_models import Service

from commands.greeteng_commands import GreetingCommands
from commands.music_commands import MusicCommands
from commands.tts_commands import TTSCommands
from commands.yandex_commands import YandexRadioCommands
from control.button_control import ButtonControl
from integrations.music.clients.yandex_client import YandexClientRepo
from integrations.music.music_fetcher import MusicFetcher
from integrations.music.player.music_player import MusicPlayer
from integrations.music.resolvers.tts.tts_resolver import TtsResolver
from integrations.music.resolvers.yandex.yandex_resolver import YandexResolver
from integrations.music.track_message_service import TrackMessageService
from potehinson_sound_core.core import Core
from potehinson_sound_core.user_interaction import UserInteraction
from scenaries.greeting_repository import GreetingRepository

SERVICE = Service(
    type="plugin",
    name="potehinson_sound_core",
    label="[🔊] Potehinson Sound Core ",
    description="Воспроизведение, управление звуками.\nПриветствие и ивенты.",
    author="Uto4ka404",
    version="0.0.1",
    site="https://potehinson-sound-core",
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    nats_url: str = "nats://localhost:4222"
    greeting_enabled: bool = False
    greeting_sound: str = "sounds/audio.mp3"
    greeting_json_path: str = "../data/scenaries/greeting.json"
    tts_host: str = "0.0.0.0"
    tts_port: int = 8000

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            nats_url=os.getenv("NATS_URL", defaults.nats_url),
            greeting_enabled=_env_bool("GREETING"),
            greeting_sound=os.getenv("GREETING_SOUND") or defaults.greeting_sound,
            greeting_json_path=os.getenv("GREETING_JSON_PATH", defaults.greeting_json_path),
            tts_host=os.getenv("TTS_HOST", defaults.tts_host),
            tts_port=int(os.getenv("TTS_PORT", defaults.tts_port)),
        )


def create_plugin(settings: Settings, nats: NatsClient | None = None) -> Plugin:
    plugin = Plugin(SERVICE, nats_url=settings.nats_url, nats=nats)

    core = Core(plugin.nats)
    player = MusicPlayer(core)
    yandex = YandexClientRepo()
    fetcher = MusicFetcher([TtsResolver(), YandexResolver(yandex)])
    greetings = GreetingRepository(settings.greeting_json_path, default_sound_url=settings.greeting_sound)

    # Карточка "Сейчас играет" в текстовом канале
    track_messages = TrackMessageService(plugin.discord, player)
    player.on_track_change(track_messages.on_music_change)
    player.on_track_end(track_messages.on_music_end)

    plugin.register(
        GreetingCommands(greetings),
        MusicCommands(player, fetcher),
        YandexRadioCommands(yandex, plugin.commands, player),
        TTSCommands(fetcher, player),
        ButtonControl(player, yandex),
    )
    plugin.add_lifespan(UserInteraction(core, plugin.nats, settings.greeting_enabled, greetings))
    return plugin
