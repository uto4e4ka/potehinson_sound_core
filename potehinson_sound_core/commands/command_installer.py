from typing import Optional

from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.net_models.discord_models import (
    Command,
    CommandArgument,
    ExecutedCommand,
    NatsMessage,
    DiscordMessageResponse,
    ExecutedCommandResponse,
)
from potehinsonnet.setup.command_registrator import CommandRegistrator, command
from yandex_music import ClientAsync

from exeptions.playing_execptions import PlayingException
from integrations.music.clients.yandex_client import YandexClientRepo
from integrations.music.music_embeds import get_music_embed
from integrations.music.music_fetcher import MusicFetcher
from integrations.music.music_models import MusicAttributes
from integrations.music.radios.radio_client import RadioClient
from integrations.music.radios.yandex.yandex_radio import YandexWave
from potehinson_sound_core import music_player
from potehinson_sound_core.core import Core
from scenaries.greeting_repository import GreetingRepository, GreetingScenario


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
        self.core = core
        self.discord_provider = discord_provider
        self.greeting_repository = greeting_repository
        self.player = music_player

        # Активные сообщения с текущим треком по гильдиям: {guild_id: DiscordMessageResponse}
        self._active_track_messages: dict[int, DiscordMessageResponse] = {}

        # ЕДИНОРАЗОВАЯ регистрация событий плеера
        self.player.on_track_change(self._on_music_change)
        self.player.on_track_end(self._on_music_end)
        self.yandex_client_repo = yandex_client_repo
        self.radio_client:RadioClient = RadioClient(self.core)
        self.radio_client.add_track_change_listener(self._on_music_change)
    # --- Вспомогательные методы ---

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

    # --- События плеера ---

    async def _on_music_change(
        self, guild_id: int, text_channel_id: int, item: MusicAttributes
    ) -> None:
        """Событие: Начал играть новый трек"""
        await self._on_music_end(guild_id, text_channel_id, item)

        try:
            raw_response = await self.discord_provider.send_message(
                NatsMessage(
                    text="",
                    embeds=[await get_music_embed(item)],
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
        msg_response = self._active_track_messages.pop(guild_id, None)

        if msg_response:
            try:
                await self.discord_provider.remove_message(
                    channel_id=msg_response.channel_id,
                    message_id=msg_response.message_id,
                )
            except Exception as e:
                print(f"[CommandInstaller] Ошибка удаления сообщения: {e}")

    # --- Команды (Аннотированные декоратором @command) ---

    @command(
        Command(
            name="play_channel",
            description="Проиграть в канале",
            tag="play_channel",
            permission="sound_core.play_channel",
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
    )
    async def _handle_play_channel(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        channel_id = self._get_arg_value(command, "voice_channel")
        url = self._get_arg_value(command, "url")

        if not channel_id or not url:
            raise ValueError(
                "Не переданы обязательные аргументы: voice_channel или url"
            )

        await self.core.play_sound(
            url=url,
            guild_id=command.guild.id,
        )
        return ExecutedCommandResponse(
            message=f"Воспроизведение {url} в канале <#{channel_id}> началось.",
            ephemeral=True,
            is_final=True,
        )

    @command(
        Command(
            name="play",
            description="Проиграть у себя",
            tag="play",
            permission="sound_core.play",
            ephemeral=True,
            args=[
                CommandArgument(
                    name="url",
                    required=True,
                    type="string",
                    description="Прямая ссылка на звук",
                )
            ],
        )
    )
    async def _handle_play(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        if not command.user or not command.user.voice_channel:
            return ExecutedCommandResponse(
                message="❌ Нужно находиться в голосовом канале", is_final=True
            )

        url = self._get_arg_value(command, "url") or ""

        try:
            embed = await self.player.play_music_to_chanel(
                url,
                command.user.voice_channel.id,
                command.guild.id,
                command.channel.id,
            )
            return ExecutedCommandResponse(embeds=[embed], is_final=True)
        except (PlayingException, FileNotFoundError) as e:
            return ExecutedCommandResponse(
                message=f"❌ Ошибка воспроизведения: `{e}`", is_final=True
            )


    @command(
        Command(
            name="add",
            description="Добавить приветствие для пользователя",
            tag="add_greeting",
            group="greeting",
            permission="sound_core.add",
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

    @command(
        Command(
            name="remove",
            description="Удалить приветствие для пользователя",
            tag="remove_greeting",
            group="greeting",
            permission="sound_core.remove",
            args=[
                CommandArgument(
                    name="user",
                    required=True,
                    type="user",
                    description="Пользователь",
                ),
            ],
        )
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
                message=f"Удалено приветствие у <@{user_id}>", is_final=True
            )
        except KeyError:
            return ExecutedCommandResponse(
                message=f"У <@{user_id}> не установлено приветствий",
                is_final=True,
            )

    @command(
        Command(
            name="disable",
            description="Выключить/Включить приветствие пользователю",
            tag="greeting_disable",
            group="greeting",
            permission="sound_core.disable",
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

    @command(
        Command(
            name="say",
            description="Сказать",
            tag="ask",
            permission="sound_core.say",
            args=[
                CommandArgument(
                    name="text",
                    required=True,
                    type="text",
                    description="Сообщение",
                ),
            ],
        )
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
            await self.core.check_and_connect(
                channel_id=command.user.voice_channel.id,
                force=True,
                guild_id=command.guild.id,
            )
            await self.core.play_sound(
                url=f"http://localhost:8000/tts?text={text}&voice=ru-RU-DmitryNeural",
                guild_id=command.guild.id,
            )
            return ExecutedCommandResponse(
                message="▶️ Начинаю говорить", is_final=True
            )
        except PlayingException as e:
            return ExecutedCommandResponse(
                message=f"❌ Ошибка воспроизведения: `{e}`", is_final=True
            )

    @command(
        Command(
            name="pause",
            description="Пауза",
            tag="pause",
            permission="sound_core.pause",
        )
    )
    async def _handle_pause_sound(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        await self.player.pause_track(command.guild.id)
        return ExecutedCommandResponse(
            message="Трек остановлен", is_final=True
        )

    @command(
        Command(
            name="resume",
            description="Продолжить",
            tag="resume",
            permission="sound_core.resume",
        )
    )
    async def _handle_resume_sound(
        self, command: ExecutedCommand
    ) -> ExecutedCommandResponse:
        await self.player.resume_track(command.guild.id)
        return ExecutedCommandResponse(
            message="Проигрывание восстановлено", is_final=True
        )

    @command(
        Command(
            name="skip",
            description="Пропустить трек",
            tag="skip",
            permission="sound_core.skip",
        )
    )
    async def _skip_track(self,command: ExecutedCommand) -> ExecutedCommandResponse:
        await self.player.skip_track(command.guild.id)
        return ExecutedCommandResponse(
            message="Пропускаю трек...", is_final=True
        )
    @command(
        Command(
            name="wave",
            group="yandex",
            tag="yandex_wave",
            permission="sound_core.yandex.wave",
            description="Запуск моей волны"
        )
    )
    async def _stream_yandex(self,command: ExecutedCommand) -> ExecutedCommandResponse:
        await self.command_registrator.reply(command.entity_id,"Запускаю волну...")
        yandex: ClientAsync = await self.yandex_client_repo.get_async_music_client(user_id= command.user.id)
        wave = YandexWave(yandex)
        await wave.init("user","onyourwave",)
        await self.radio_client.stream_to_channel(wave,command.user.voice_channel.id,command.guild.id,command.channel.id)
        return ExecutedCommandResponse(message="Стрим запущен")
    # --- Управление жизненным циклом ---

    @command(
        Command(
            name="skip",
            group="yandex",
            tag="yandex_skip",
            permission="sound_core.yandex.wave",
            description="Пропустить трек моей волны"
        )
    )
    async def _stream_yandex_skip(self,command: ExecutedCommand) -> ExecutedCommandResponse:
        await self.command_registrator.reply(command.entity_id,"Пропускаю...")
        await self.radio_client.skip(command.guild.id)
        return ExecutedCommandResponse(message="Трек пропущен")

    async def start(self,service) -> None:
        """Автоматически регистрирует все декорированные методы этого инстанса."""
        await self.command_registrator.register_instance_commands(self)

    async def stop(self) -> None:
        """Отписывает подписки через CommandRegistrator."""
        print("Removing commands...")
        await self.command_registrator.close()