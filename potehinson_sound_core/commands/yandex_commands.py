from potehinsonnet.net_models.discord_models import Command, ExecutedCommand, ExecutedCommandResponse
from potehinsonnet.setup.command_registrator import CommandRegistrator, command
from integrations.music.clients.yandex_client import YandexClientRepo
from integrations.music.radios.radio_client import RadioClient
from integrations.music.radios.yandex.yandex_radio import YandexWave


class YandexRadioCommands:
    def __init__(
            self,
            radio_client: RadioClient,
            yandex_repo: YandexClientRepo,
            registrator: CommandRegistrator
    ):
        self.radio_client = radio_client
        self.yandex_repo = yandex_repo
        self.registrator = registrator

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

        await self.registrator.reply(command.entity_id, "Запускаю волну...")
        client = await self.yandex_repo.get_async_music_client(user_id=command.user.id)

        wave = YandexWave(client)
        await wave.init("user", "onyourwave",)
        await self.radio_client.stream_to_channel(
            wave, command.user.voice_channel.id, command.guild.id, command.channel.id
        )
        return ExecutedCommandResponse(message=f"🌊 Волна запущена")

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
        await self.radio_client.skip(command.guild.id)
        return ExecutedCommandResponse(message="⏭️ Пропущено", is_final=True)

