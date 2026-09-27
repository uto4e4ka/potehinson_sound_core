from potehinsonnet.setup.command_registrator import CommandRegistrator
from potehinsonnet.discord_provider import DiscordProvider
from potehinson_sound_core import music_player
from potehinson_sound_core.core import Core

from integrations.music.clients.yandex_client import YandexClientRepo
from integrations.music.radios.radio_client import RadioClient
from integrations.music.track_message_service import TrackMessageService
from scenaries.greeting_repository import GreetingRepository

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
        music_player: music_player.MusicPlayer,
        yandex_client_repo: YandexClientRepo,
    ) -> None:
        self.command_registrator = command_registrator

        # Общие сервисы
        self.track_message_service = TrackMessageService(discord_provider)
        self.radio_client = RadioClient(core)

        # Связываем события
        music_player.on_track_change(self.track_message_service.on_music_change)
        music_player.on_track_end(self.track_message_service.on_music_end)
        self.radio_client.add_track_change_listener(self.track_message_service.on_music_change)

        # Создаём экземпляры модулей с командами
        self.controllers = [
            GreetingCommands(greeting_repository),
            MusicCommands(music_player, core),
            YandexRadioCommands(self.radio_client, yandex_client_repo, command_registrator),
        ]

    async def start(self, service=None) -> None:
        """Регистрируем каждый контроллер отдельно."""
        for controller in self.controllers:
            await self.command_registrator.register_instance_commands(controller)

    async def stop(self) -> None:
        """Завершаем работу регистратора."""
        print("Removing commands...")
        await self.command_registrator.close()