from potehinsonnet.setup.command_registrator import CommandRegistrator
from potehinsonnet.discord_provider import DiscordProvider

from integrations.music.music_fetcher import MusicFetcher
from integrations.music.player.music_player import  MusicPlayer
from potehinson_sound_core.core import Core

from integrations.music.clients.yandex_client import YandexClientRepo
from integrations.music.track_message_service import TrackMessageService
from scenaries.greeting_repository import GreetingRepository
from .tts_commands import TTSCommands

# Импортируем наши новые модули команд:
from ..commands.greeteng_commands import GreetingCommands
from ..commands.music_commands import MusicCommands
from ..commands.yandex_commands import YandexRadioCommands


class CommandInstaller:
    def __init__(
        self,
        command_registrator: CommandRegistrator,
        core: Core,
        discord_provider: DiscordProvider,
        greeting_repository: GreetingRepository,
        music_player: MusicPlayer,
        yandex_client_repo: YandexClientRepo,
        music_fetcher: MusicFetcher
    ) -> None:
        self.command_registrator = command_registrator

        # Общие сервисы
        self.track_message_service = TrackMessageService(discord_provider)

        # Связываем события
        music_player.on_track_change(self.track_message_service.on_music_change)
        music_player.on_track_end(self.track_message_service.on_music_end)

        # Создаём экземпляры модулей с командами
        self.controllers = [
            GreetingCommands(greeting_repository),
            MusicCommands(music_player,music_fetcher, core),
            YandexRadioCommands(yandex_client_repo, command_registrator,music_player),
            TTSCommands(core)
        ]

    async def start(self, service=None) -> None:
        """Регистрируем каждый контроллер отдельно."""
        for controller in self.controllers:
            await self.command_registrator.register_instance_commands(controller)

    async def stop(self) -> None:
        """Завершаем работу регистратора."""
        print("Removing commands...")
        await self.command_registrator.close()