"""Сборка плагина: все объекты создаются здесь, в одном месте и в явном порядке."""
from potehinsonnet import Plugin
from potehinsonnet.net import NatsClient
from potehinsonnet.manifest import load_manifest
from potehinsonnet.net_models.system_models import Service

from potehinson_sound_core.core import Core
from potehinson_sound_core.greetings.commands import GreetingCommands
from potehinson_sound_core.greetings.listener import UserInteraction
from potehinson_sound_core.greetings.repository import GreetingRepository
from potehinson_sound_core.music.buttons import ButtonControl
from potehinson_sound_core.music.commands import MusicCommands
from potehinson_sound_core.music.fetcher import MusicFetcher
from potehinson_sound_core.music.player.player import MusicPlayer
from potehinson_sound_core.music.resolvers.tts import TtsResolver
from potehinson_sound_core.music.track_messages import TrackMessageService
from potehinson_sound_core.music.yandex.client import YandexClientRepo
from potehinson_sound_core.music.yandex.resolver import YandexResolver
from potehinson_sound_core.music.yandex.wave_commands import YandexRadioCommands
from potehinson_sound_core.panel_pages import register_panel_pages
from potehinson_sound_core.settings import PROJECT_ROOT, Settings
from potehinson_sound_core.tts.commands import TTSCommands



def create_plugin(settings: Settings, nats: NatsClient | None = None, service: Service | None = None) -> Plugin:
    """Собрать плагин. Имя, версия и описание — из plugin.toml (если service не передали)."""
    plugin = Plugin(service or load_manifest(PROJECT_ROOT).service(), nats_url=settings.nats_url, nats=nats)

    core = Core(plugin.nats)
    player = MusicPlayer(core)
    yandex = YandexClientRepo()
    fetcher = MusicFetcher([TtsResolver(), YandexResolver(yandex)])
    greetings = GreetingRepository(settings.greeting_json_path, default_sound_url=settings.greeting_sound)

    # Карточка "Сейчас играет" в текстовом канале
    track_messages = TrackMessageService(plugin.discord, player)
    player.on_track_change(track_messages.on_music_change)
    player.on_track_end(track_messages.on_music_end)
    player.on_state_change(track_messages.on_state_change)

    plugin.register(
        GreetingCommands(greetings),
        MusicCommands(player, fetcher),
        YandexRadioCommands(yandex, plugin.commands, player),
        TTSCommands(fetcher, player),
        ButtonControl(player, yandex),
    )
    plugin.add_lifespan(UserInteraction(core, plugin.nats, settings.greeting_enabled, greetings))
    register_panel_pages(plugin, core, player, greetings)
    return plugin
