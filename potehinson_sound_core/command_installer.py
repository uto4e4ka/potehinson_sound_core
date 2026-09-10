from typing import Callable, Awaitable

from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.net_models.discord_models import Command, CommandArgument, ExecutedCommand, EmbedImage, \
    EmbedThumbnail
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
                    image=EmbedImage(
                        url = "https://avatars.yandex.net/get-music-content/20622967/10e341a4.a.43788606-2/50x50",
                        height=50,
                        width=50
                    ),
                    author=EmbedAuthor(
                        name="Author",
                        icon_url="https://avatars.yandex.net/get-music-content/20622967/10e341a4.a.43788606-2/50x50"
                    ),
                    footer=EmbedFooter(
                        text="Footer",
                    ),
                    thumbnail=EmbedThumbnail(
                        url="https://avatars.yandex.net/get-music-content/20622967/10e341a4.a.43788606-2/50x50"
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
    async def _handle_ask(self,command: ExecutedCommand) -> ExecutedCommandResponse:
        if not command.user.voice_channel:
            return ExecutedCommandResponse(
                message="❌Нужно находится в голосовом канале"
            )
        text = self._get_arg_value(command, "text") or ""
        await self.core.play_sound(
            url=f"http://localhost:8000/tts?text={text}&voice=ru-RU-DmitryNeural",
            channel_id=command.user.voice_channel.id,
            guild_id=command.guild.id,
        )
        return ExecutedCommandResponse(
            message="▶️ Начинаю говорить"
        )
    def get_commands(self) -> list[tuple[Command, Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse]]]]:
        """Возвращает список пар (Command, Handler) для регистрации."""
        play_channel_command = Command(
            name="play_channel",
            description="Проиграть в канале",
            tag="play_channel",
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
            name="add",
            description="Добавить приветствие для пользователя",
            tag="add_greeting",
            group="greeting",
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
            name="remove",
            description="Удалить приветствие для пользователя",
            tag="remove_greeting",
            group="greeting",
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
        disable_greeting = Command(
            name="disable",
            description="Выключить/Включить приветствие пользователю",
            tag="greeting_disable",
            group="greeting",
            permission="sound_core.disable",
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
                    type="bool",
                    description="Выключить/Включить"
                )
            ]
        )
        ask = Command(
            name="say",
            description="Сказать",
            tag="ask",
            service=self.command_registrator.plugin_name,
            args=[
                CommandArgument(
                    name="text",
                    required=True,
                    type="text",
                    description="Сообщение"
                ),
            ]
        )
        # Возвращаем список кортежей (Команда, Функция-обработчик)
        return [
            (play_channel_command, self._handle_play_channel),
            (play_command, self._handle_play),
            (add_binding,self._handle_greeting_install),
            (remove_binding,self._handle_greeting_delete),
            (disable_greeting,self._handle_disable_greeting),
            (ask, self._handle_ask),
        ]

    async def start(self, plugin) -> None:
        try:
           await self.command_registrator.register_command(self.get_commands())
        except KeyError as e:
            plugin(f"Error while registering command: . Skipping...")

    async def stop(self) -> None:
        print("Removing commands...")
        await self.command_registrator.unregister_command(self.get_commands())

