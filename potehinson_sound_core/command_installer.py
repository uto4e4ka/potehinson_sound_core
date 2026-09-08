from typing import List, Callable, Awaitable

from nats.protocol import command
from potehinsonnet.monitoring.health import Health
from potehinsonnet.net_models.discord_models import Command, CommandArgument, ExecutedCommand
from potehinsonnet.setup.command_registrator import CommandRegistrator

from potehinson_sound_core.core import Core


class CommandInstaller:
    def __init__(self,command_registrator:CommandRegistrator,core:Core) -> None:
        self.command_registrator = command_registrator
        self.core = core

    def _get_arg_value(self, command: ExecutedCommand, arg_name: str) -> str | None:
        """Вспомогательный метод для безопасного извлечения аргумента по имени."""
        for arg in command.args:
            if arg.name == arg_name:
                return arg.value
        return None

    async def _handle_play_channel(self, body: dict) -> None:
        """Отдельный обработчик для команды play_channel."""
        command = ExecutedCommand.model_validate(body)
        print(body)

        channel_id = self._get_arg_value(command, "voice_channel")
        url = self._get_arg_value(command, "url")

        if not channel_id or not url:
            raise ValueError("Не переданы обязательные аргументы: voice_channel или url")

        await self.core.play_sound(
            url=url,
            channel_id=int(channel_id),
            guild_id=command.guild.id,
        )

    def get_commands(self) -> list[tuple[Command, Callable[[dict], Awaitable[None]]]]:
        """Возвращает список пар (Command, Handler) для регистрации."""
        play_command = Command(
            name="play_channel",
            description="Проиграть в канале",
            tag="play",
            service=self.command_registrator.plugin_name,
            args=[
                CommandArgument(
                    name="voice_channel",
                    required=True,
                    type="voice_channel",
                    description="Канал для проигрывания музыки",
                ),
                CommandArgument(
                    name="url",
                    required=True,
                    type="string",
                    description="Прямая ссылка на звук"
                ),
            ],
        )

        # Возвращаем список кортежей (Команда, Функция-обработчик)
        return [
            (play_command, self._handle_play_channel)
        ]

    async def start(self,plugin) -> None:
        for command,callback in self.get_commands():
            await self.command_registrator.register_command(
                command=command,
                listener=callback,
            )
    async def stop(self) -> None:
        return