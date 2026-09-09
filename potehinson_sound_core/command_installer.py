from typing import Callable, Awaitable

from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.net_models.discord_models import Command, CommandArgument, ExecutedCommand
from potehinsonnet.net_models.discord_models import ExecutedCommandResponse, Embed, EmbedField
from potehinsonnet.net_models.discord_models import  EmbedAuthor, EmbedFooter
from potehinsonnet.setup.command_registrator import CommandRegistrator

from potehinson_sound_core.core import Core
from scenaries.greeting_repository import GreetingRepository, GreetingScenario


class CommandInstaller:
    def __init__(self, command_registrator: CommandRegistrator, core: Core, discord_provider: DiscordProvider,greeting_repository:GreetingRepository) -> None:
        self.command_registrator = command_registrator
        self.core = core
        self.discord_provider = discord_provider
        self.greeting_repository = greeting_repository

    def _get_arg_value(self, command: ExecutedCommand, arg_name: str) -> str | None:
        """Вспомогательный метод для безопасного извлечения аргумента по имени."""
        for arg in command.args:
            if arg.name == arg_name:
                return arg.value
        return None

    async def _handle_play_channel(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        """Отдельный обработчик для команды play_channel."""
        channel_id = self._get_arg_value(command, "voice_channel")
        url = self._get_arg_value(command, "url")

        if not channel_id or not url:
            raise ValueError("Не переданы обязательные аргументы: voice_channel или url")

        await self.core.play_sound(
            url=url,
            channel_id=int(channel_id),
            guild_id=command.guild.id,
        )
        return ExecutedCommandResponse(
            message=f"Воспроизведение {url} в канале <#{channel_id}> началось.",
            ephemeral=True,
        )

    async def _handle_play(self, command: ExecutedCommand) -> ExecutedCommandResponse:

        if not command.user.voice_channel:
            return ExecutedCommandResponse(
                message="❌Нужно находится в голосовом канале"
            )
        url = self._get_arg_value(command, "url") or ""

        await self.core.play_sound(
            url=url,
            channel_id=command.user.voice_channel.id,
            guild_id=command.guild.id,
        )
        return ExecutedCommandResponse(
            message="Test",
            embeds=[
                Embed(
                    title="Title",
                    description="Description",
                    color=0xFF69B4,
                    url="https://penis.com",
                    author=EmbedAuthor(
                        name="Author",
                    ),
                    footer=EmbedFooter(
                        text="Footer",
                    ),
                    fields=[
                        EmbedField(
                            name="test", value="<t:1700000000:R>"
                        ),
                        EmbedField(
                            name="test", value="<t:1700000000:R>"
                        )
                    ]
                )
            ],
            ephemeral=True,
        )

    async def _handle_greeting_install(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        url = self._get_arg_value(command, "url") or ""
        user_id = self._get_arg_value(command, "user") or ""
        try:
            self.greeting_repository.set_greeting(
                GreetingScenario(
                user_id=int(user_id),
                guild_id = command.guild.id,
                sound_url=url
                )
            )
            return ExecutedCommandResponse(
                message=f"Добавлено новое приветствие для <@{user_id}>",
            )
        except FileNotFoundError as e:
            return ExecutedCommandResponse(
                message=f"Ошибка добавления приветствия для <@{user_id}>",
            )

    async def _handle_greeting_delete(self,command: ExecutedCommand) -> ExecutedCommandResponse:
        user_id = int(self._get_arg_value(command, "user") or "")
        guild_id = command.guild.id
        try:
            self.greeting_repository.remove_greeting(user_id=user_id,guild_id=guild_id)
            return ExecutedCommandResponse(
                message=f"Удалено приветствие у <@{user_id}>",
            )
        except KeyError as e:
            return ExecutedCommandResponse(
                message=f"У <@{user_id}> не установлено приветствий",
            )
    async def _handle_disable_greeting(self,command: ExecutedCommand) -> ExecutedCommandResponse:
        user_id = int(self._get_arg_value(command, "user") or "")
        guild_id = command.guild.id
        disabled = bool(self._get_arg_value(command, "disabled"))
        greeting = self.greeting_repository.get_greeting(user_id=user_id,guild_id=guild_id)
        old = greeting.disabled
        greeting.disabled = disabled
        self.greeting_repository.set_greeting(greeting)
        return ExecutedCommandResponse(
            message=f"Изменено состояние greeting.disabled {old}->{disabled} для <@{user_id}>",
        )
    def get_commands(self) -> list[tuple[Command, Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse]]]]:
        """Возвращает список пар (Command, Handler) для регистрации."""
        play_channel_command = Command(
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

        play_command = Command(
            name="play",
            description="Проиграть у себя",
            tag="play",
            service=self.command_registrator.plugin_name,
            args=[
                CommandArgument(
                    name="url",
                    required=True,
                    type="string",
                    description="Прямая ссылка на звук"
                )
            ]
        )

        add_binding = Command(
            name="add greeting",
            description="Добавить приветствие для пользователя",
            tag="add_greeting",
            service=self.command_registrator.plugin_name,
            args=[
                CommandArgument(
                    name="user",
                    required=True,
                    type="user",
                    description="Пользователь"
                ),
                CommandArgument(
                    name="url",
                    required=True,
                    type="string",
                    description="Прямая ссылка на звук"
                )
            ]
        )

        remove_binding = Command(
            name="remove greeting",
            description="Удалить приветствие для пользователя",
            tag="remove_greeting",
            service=self.command_registrator.plugin_name,
            args=[
                CommandArgument(
                    name="user",
                    required=True,
                    type="user",
                    description="Пользователь"
                ),
                CommandArgument(
                    name="disabled",
                    required=True,
                    type="user",
                    description="ВЫ"
                )
            ]
        )
        disable_greeting = Command(
            name="disable greeting",
            description="Выключить/Включить приветствие пользователю",
            tag="disable_greeting",
            service=self.command_registrator.plugin_name,
            args=[
                CommandArgument(
                    name="user",
                    required=True,
                    type="user",
                    description="Пользователь"
                ),

            ]
        )
        # Возвращаем список кортежей (Команда, Функция-обработчик)
        return [
            (play_channel_command, self._handle_play_channel),
            (play_command, self._handle_play),
            (add_binding,self._handle_greeting_install),
            (remove_binding,self._handle_greeting_delete)
        ]

    async def start(self, plugin) -> None:
        for command, callback in self.get_commands():
            await self.command_registrator.register_command(
                command=command,
                listener=callback,
            )

    async def stop(self) -> None:
        return
