from potehinsonnet.net_models.discord_models import Command, CommandArgument, ExecutedCommand, ExecutedCommandResponse, \
    ComponentButton, ActionRow, Separator, TextDisplay, Container, ComponentButtonStyle
from potehinsonnet.setup.command_registrator import command

from integrations.music.music_fetcher import MusicFetcher
from integrations.music.player import music_player
from integrations.music.player.providers.queue_stream_provider import QueueStreamProvider
from potehinson_sound_core.core import Core
from exeptions.playing_execptions import PlayingException


class MusicCommands:
    def __init__(self, player: music_player.MusicPlayer, music_fetcher: MusicFetcher, core: Core):
        self.player = player
        self.core = core
        self.music_fetcher = music_fetcher
        # Храним отдельный провайдер очереди для каждого сервера (guild_id)
        self.providers: dict[int, QueueStreamProvider] = {}

    def _ensure_voice(self, command: ExecutedCommand) -> int:
        if not command.user or not command.user.voice_channel:
            raise PlayingException("❌ Нужно находиться в голосовом канале")
        return command.user.voice_channel.id

    def _get_or_create_provider(self, guild_id: int) -> QueueStreamProvider:
        """Гарантирует уникальную очередь для каждого сервера."""
        if guild_id not in self.providers:
            self.providers[guild_id] = QueueStreamProvider(self.music_fetcher)
        return self.providers[guild_id]

    @command(
        Command(
            name="play",
            description="Проиграть трек",
            tag="play",
            permission="sound_core.play",
            ephemeral=True,
            args=[CommandArgument(name="url", required=True, type="string", description="Ссылка")],
        )
    )
    async def handle_play(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        try:
            channel_id = self._ensure_voice(command)
            guild_id = command.guild.id
            url = next((a.value for a in command.args if a.name == "url"), "")

            provider = self._get_or_create_provider(guild_id)
            embed = await provider.add_music(url)

            self.player.set_provider(guild_id, provider=provider)
            await self.player.add_to_channel_player(
                channel_id, guild_id, command.channel.id
            )
            return ExecutedCommandResponse(embeds=[embed],

                                           is_final=True)
        except Exception as e:
            return ExecutedCommandResponse(message=f"❌ {e}", is_final=True)

    @command(
        Command(name="skip", description="Пропустить трек", tag="skip", permission="sound_core.skip")
    )
    async def handle_skip(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        await self.player.skip_track(command.guild.id)
        return ExecutedCommandResponse(message="⏭️ Пропущено", is_final=True)

    @command(
        Command(
            name="pause",
            tag="pause",
            description="Пауза",
            permission="sound_core.pause",
        )
    )
    async def pause(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        await self.player.pause_track(command.guild.id)
        return ExecutedCommandResponse(message="⏸️ Пауза", is_final=True)

    @command(
        Command(
            name="resume",
            tag="resume",
            description="Продолжить",
            permission="sound_core.resume",
        )
    )
    async def resume(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        await self.player.resume_track(command.guild.id)
        return ExecutedCommandResponse(message="▶️ Возобновляем", is_final=True)

    @command(
        Command(
            name="shuffle",
            tag="shuffle",
            description="Перемешать",
            permission="sound_core.shuffle",
        )
    )
    async def shuffle(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        provider = self._get_or_create_provider(command.guild.id)
        is_shuffled = provider.shuffle_queue()

        if is_shuffled:
            return ExecutedCommandResponse(message="🔀 Случайное воспроизведение включено", is_final=True)
        return ExecutedCommandResponse(message="➡️ Случайное воспроизведение отключено", is_final=True)

    @command(
        Command(
            name="previous",
            description="Вернуться к предыдущему треку",
            tag="previous",
            permission="sound_core.previous",
        )
    )
    async def handle_previous(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        guild_id = command.guild.id
        success = await self.player.previous_track(guild_id)
        if success:
            return ExecutedCommandResponse(
                message="⏮️ Возвращаемся к предыдущему треку", is_final=True
            )
        return ExecutedCommandResponse(
            message="❌ Не удалось переключить трек", is_final=True
        )

    @command(
        Command(
            name="say",
            tag="say",
            description="Сказать",
            permission="sound_core.tts.say",
            args=[
                CommandArgument(
                    name="text",
                    description="Текст",
                    required=True,
                    type="string",
                )
            ],
        )
    )
    async def say(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        try:
            channel_id = self._ensure_voice(command)
            guild_id = command.guild.id
            text = next((a.value for a in command.args if a.name == "text"), "")

            provider = self._get_or_create_provider(guild_id)
            await provider.add_music(f"http://localhost:8000/integrations/tts?text={text}&voice=ru-RU-DmitryNeural")

            self.player.set_provider(guild_id, provider=provider)
            await self.player.add_to_channel_player(
                channel_id, guild_id, command.channel.id
            )
            return ExecutedCommandResponse(message="🗣️ Начинаю говорить", is_final=True)
        except Exception as e:
            return ExecutedCommandResponse(message=f"❌ {e}", is_final=True)