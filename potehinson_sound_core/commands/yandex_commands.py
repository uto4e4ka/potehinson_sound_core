from potehinsonnet.net_models.discord_models import Command, ExecutedCommand, ExecutedCommandResponse
from potehinsonnet.setup.command_registrator import CommandRegistrator, command
from integrations.music.clients.yandex_client import YandexClientRepo
from integrations.music.player.music_player import MusicPlayer
from integrations.music.player.providers.radio_stream_provider import RadioStreamProvider
from integrations.music.radios.yandex.yandex_radio import YandexWave


class YandexRadioCommands:
    def __init__(
            self,
            yandex_repo: YandexClientRepo,
            registrator: CommandRegistrator,
            music_player: MusicPlayer,
    ):
        self.yandex_repo = yandex_repo
        self.registrator = registrator
        self.music_player = music_player
        # Храним RadioStreamProvider отдельно для каждой гильдии (guild.id)
        self.radio_providers: dict[int, RadioStreamProvider] = {}

    @command(
        Command(
            name="yandex",
            group="wave",
            tag="yandex_wave",
            permission="sound_core.wave.yandex",
            description="Запуск Моей Волны",
        )
    )
    async def handle_wave(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        if not command.user or not command.user.voice_channel:
            return ExecutedCommandResponse(message="❌ Зайдите в голосовой канал", is_final=True)

        guild_id = command.guild.id
        await self.registrator.reply(command.entity_id, "Запускаю волну...")

        try:
            client = await self.yandex_repo.get_async_music_client(user_id=command.user.id)

            wave = YandexWave(client)
            await wave.init("user", "onyourwave")

            # Создаем и запоминаем провайдер волны для конкретной гильдии
            radio_provider = RadioStreamProvider(wave)
            self.radio_providers[guild_id] = radio_provider

            self.music_player.set_provider(guild_id, radio_provider)
            await self.music_player.add_to_channel_player(
                command.user.voice_channel.id,
                guild_id,
                command.channel.id
            )
            return ExecutedCommandResponse(message="🌊 Волна запущена", is_final=True)
        except Exception as e:
            return ExecutedCommandResponse(message=f"❌ Ошибка запуска волны: {e}", is_final=True)

    @command(
        Command(
            name="skip",
            group="wave",
            tag="wave_skip",
            permission="sound_core.wave.skip",
            description="Пропустить трек в волне",
        )
    )
    async def handle_skip(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        await self.music_player.skip_track(command.guild.id)
        return ExecutedCommandResponse(message="⏭️ Пропущено", is_final=True)

    # @command(
    #     Command(
    #         name="stop",
    #         group="wave",
    #         tag="wave_stop",
    #         permission="sound_core.wave.stop",
    #         description="Остановить Мою Волну",
    #     )
    # )
    # async def handle_stop(self, command: ExecutedCommand) -> ExecutedCommandResponse:
    #     guild_id = command.guild.id
    #
    #     # Останавливаем плеер и удаляем провайдер гильдии
    #     await self.music_player.stop_track(guild_id)
    #     self.radio_providers.pop(guild_id, None)
    #
    #     return ExecutedCommandResponse(message="⏹️ Волна остановлена", is_final=True)