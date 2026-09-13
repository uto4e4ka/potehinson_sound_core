import asyncio
from typing import Callable, Awaitable, Optional
from integrations import yandex_resolver

from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.net_models.discord_models import (
    Command,
    CommandArgument,
    ExecutedCommand,
    EmbedImage,
    EmbedThumbnail,
    NatsMessage,
    DiscordMessageRemove,
    DiscordMessageResponse,
    ExecutedCommandResponse,
    Embed,
    EmbedField,
    EmbedAuthor,
    EmbedFooter,
)
from potehinsonnet.setup.command_registrator import CommandRegistrator

from exeptions.playing_execptions import PlayingException
from integrations.music_models import MusicQueueItem, MusicAttributes
from potehinson_sound_core import sound_classificator, music_player
from potehinson_sound_core.core import Core
from scenaries.greeting_repository import GreetingRepository, GreetingScenario


class CommandInstaller:

    def __init__(
        self,
        command_registrator: CommandRegistrator,
        core: Core,
        discord_provider: DiscordProvider,
        greeting_repository: GreetingRepository,
    ) -> None:
        self.command_registrator = command_registrator
        self.core = core
        self.discord_provider = discord_provider
        self.greeting_repository = greeting_repository
        self.player = music_player.MusicPlayer(core=self.core)

        # Активные сообщения с текущим треком по гильдиям: {guild_id: DiscordMessageResponse}
        self._active_track_messages: dict[int, DiscordMessageResponse] = {}

        # ЕДИНОРАЗОВАЯ регистрация событий плеера
        self.player.on_track_change(self._on_music_change)
        self.player.on_track_end(self._on_music_end)

    def _get_arg_value(
        self, command: ExecutedCommand, arg_name: str
    ) -> str | None:
        """Вспомогательный метод для безопасного извлечения аргумента по имени."""
        for arg in command.args:
            if arg.name == arg_name:
                return arg.value
        return None

    def _get_bool_arg(self, command: ExecutedCommand, arg_name: str) -> bool:
        value = self._get_arg_value(command, arg_name)

        if value is None:
            return False

        if isinstance(value, bool):
            return value

        value = value.lower().strip()

        if value == "true":
            return True

        if value == "false":
            return False

        raise ValueError(f"Некорректное значение bool: {value}")

    async def _handle_play_channel(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        """Отдельный обработчик для команды play_channel."""
        channel_id = self._get_arg_value(command, "voice_channel")
        url = self._get_arg_value(command, "url")

        if not channel_id or not url:
            raise ValueError(
                "Не переданы обязательные аргументы: voice_channel или url"
            )

        await self.core.play_sound(
            url=url,
            channel_id=int(channel_id),
            guild_id=command.guild.id,
        )
        return ExecutedCommandResponse(
            message=f"Воспроизведение {url} в канале <#{channel_id}> началось.",
            ephemeral=True,
            is_final=True,
        )

    async def _on_music_change(
        self, guild_id: int, text_channel_id: int, item: MusicAttributes
    ) -> None:
        """Событие: Начал играть новый трек"""
        # Если старое сообщение еще висит — очищаем его
        await self._on_music_end(guild_id, text_channel_id, item)

        try:
            raw_response = await self.discord_provider.send_message(
                NatsMessage(
                    text="",
                    embeds=[await sound_classificator.get_music_embed(item)],
                    service="",
                    channel_id=text_channel_id,
                )
            )
            self._active_track_messages[guild_id] = (
                DiscordMessageResponse.model_validate(raw_response)
            )
        except Exception as e:
            print(f"[CommandInstaller] Ошибка отправки карточки: {e}")

    async def _on_music_end(
        self, guild_id: int, text_channel_id: int, item: MusicAttributes
    ) -> None:
        """Событие: Трек закончился или был пропущен"""
        print(f"Removing track message for guild {guild_id}")
        msg_response = self._active_track_messages.pop(guild_id, None)

        if msg_response:
            try:
                await self.discord_provider.remove_message(
                    channel_id=msg_response.channel_id,
                    message_id=msg_response.message_id,
                )
            except Exception as e:
                print(f"[CommandInstaller] Ошибка удаления сообщения: {e}")

    async def _handle_play(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        if not command.user or not command.user.voice_channel:
            await self.command_registrator.reply(command.entity_id,ExecutedCommandResponse(
                    message="❌ Нужно находиться в голосовом канале", is_final=True
                )
            )

        url = self._get_arg_value(command, "url") or ""
        # if not url:
        #     return ExecutedCommandResponse(
        #         message="❌ Укажите ссылку на аудиозапись", is_final=True
        #     )

        try:
            res_msg = await self.player.add_music(
                url=url,
                channel_id=command.user.voice_channel.id,
                text_channel_id=command.channel.id,
                guild_id=command.guild.id,
            )
            await self.command_registrator.reply(command.entity_id,ExecutedCommandResponse(
                    message=f"✅ {res_msg}", is_final=True
                )
            )
        except PlayingException as e:
            await self.command_registrator.reply(command.entity_id, ExecutedCommandResponse(
                message=f"❌ Ошибка воспроизведения: `{e}`", is_final=True
            )
                                                 )

        return ExecutedCommandResponse(
                message=f"❌ Непредвиденная ошибка:", is_final=True
        )

    async def _handle_greeting_install(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        url = self._get_arg_value(command, "url") or ""
        user_id = self._get_arg_value(command, "user") or ""
        try:
            self.greeting_repository.set_greeting(
                GreetingScenario(
                    user_id=int(user_id),
                    guild_id=command.guild.id,
                    sound_url=url,
                )
            )
            return ExecutedCommandResponse(
                message=f"Добавлено новое приветствие для <@{user_id}>",
                is_final=True,
            )
        except FileNotFoundError:
            return ExecutedCommandResponse(
                message=f"Ошибка добавления приветствия для <@{user_id}>",
                is_final=True,
            )

    async def _handle_greeting_delete(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        user_id = int(self._get_arg_value(command, "user") or "0")
        guild_id = command.guild.id
        try:
            self.greeting_repository.remove_greeting(
                user_id=user_id, guild_id=guild_id
            )
            return ExecutedCommandResponse(
                message=f"Удалено приветствие у <@{user_id}>",
                is_final=True,
            )
        except KeyError:
            return ExecutedCommandResponse(
                message=f"У <@{user_id}> не установлено приветствий",
                is_final=True,
            )

    async def _handle_disable_greeting(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        user_id = int(self._get_arg_value(command, "user") or "0")
        guild_id = command.guild.id
        disabled = bool(self._get_bool_arg(command, "disabled"))
        greeting = self.greeting_repository.get_greeting(
            user_id=user_id, guild_id=guild_id
        )
        old = greeting.disabled
        greeting.disabled = disabled
        self.greeting_repository.set_greeting(greeting)
        return ExecutedCommandResponse(
            message=f"Изменено состояние greeting.disabled {old}->{disabled} для <@{user_id}>",
            is_final=True,
        )

    async def _handle_ask(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        if not command.user or not command.user.voice_channel:
            return ExecutedCommandResponse(
                message="❌ Нужно находиться в голосовом канале", is_final=True
            )
        text = self._get_arg_value(command, "text") or ""
        try:
            await self.core.play_sound(
                url=f"http://localhost:8000/tts?text={text}&voice=ru-RU-DmitryNeural",
                channel_id=command.user.voice_channel.id,
                guild_id=command.guild.id,
            )
            return ExecutedCommandResponse(
                message="▶️ Начинаю говорить", is_final=True
            )
        except PlayingException as e:
            return ExecutedCommandResponse(
                message=f"❌ Ошибка воспроизведения: `{e}`", is_final=True
            )

    def get_commands(
        self,
    ) -> list[
        tuple[
            Command,
            Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse]],
        ]
    ]:
        """Возвращает список пар (Command, Handler) для регистрации."""
        play_channel_command = Command(
            name="play_channel",
            description="Проиграть в канале",
            tag="play_channel",
            permission="sound_core.play_channel",
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
                    description="Прямая ссылка на звук",
                ),
            ],
        )

        play_command = Command(
            name="play",
            description="Проиграть у себя",
            tag="play",
            permission="sound_core.play",
            service=self.command_registrator.plugin_name,
            ephemeral=False,
            args=[
                CommandArgument(
                    name="url",
                    required=True,
                    type="string",
                    description="Прямая ссылка на звук",
                )
            ],
        )

        add_binding = Command(
            name="add",
            description="Добавить приветствие для пользователя",
            tag="add_greeting",
            group="greeting",
            permission="sound_core.add",
            service=self.command_registrator.plugin_name,
            args=[
                CommandArgument(
                    name="user",
                    required=True,
                    type="user",
                    description="Пользователь",
                ),
                CommandArgument(
                    name="url",
                    required=True,
                    type="string",
                    description="Прямая ссылка на звук",
                ),
            ],
        )

        remove_binding = Command(
            name="remove",
            description="Удалить приветствие для пользователя",
            tag="remove_greeting",
            group="greeting",
            permission="sound_core.remove",
            service=self.command_registrator.plugin_name,
            args=[
                CommandArgument(
                    name="user",
                    required=True,
                    type="user",
                    description="Пользователь",
                ),
            ],
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
                    description="Пользователь",
                ),
                CommandArgument(
                    name="disabled",
                    required=True,
                    type="bool",
                    description="Выключить/Включить",
                ),
            ],
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
                    description="Сообщение",
                ),
            ],
        )

        return [
            (play_channel_command, self._handle_play_channel),
            (play_command, self._handle_play),
            (add_binding, self._handle_greeting_install),
            (remove_binding, self._handle_greeting_delete),
            (disable_greeting, self._handle_disable_greeting),
            (ask, self._handle_ask),
        ]

    async def start(self, plugin) -> None:
        try:
            await self.command_registrator.register_command(self.get_commands())
        except KeyError:
            plugin("Error while registering command: . Skipping...")

    async def stop(self) -> None:
        print("Removing commands...")
        await self.command_registrator.unregister_command(self.get_commands())