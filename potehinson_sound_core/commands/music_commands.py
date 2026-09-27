from potehinsonnet.net_models.discord_models import Command, CommandArgument, ExecutedCommand, ExecutedCommandResponse
from potehinsonnet.setup.command_registrator import command
from potehinson_sound_core import music_player
from potehinson_sound_core.core import Core
from exeptions.playing_execptions import PlayingException

class MusicCommands:
    def __init__(self, player: music_player.MusicPlayer, core: Core):
        self.player = player
        self.core = core

    def _ensure_voice(self, command: ExecutedCommand) -> int:
        if not command.user or not command.user.voice_channel:
            raise PlayingException("❌ Нужно находиться в голосовом канале")
        return command.user.voice_channel.id

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
            url = next((a.value for a in command.args if a.name == "url"), "")
            embed = await self.player.play_music_to_chanel(
                url, channel_id, command.guild.id, command.channel.id
            )
            return ExecutedCommandResponse(embeds=[embed], is_final=True)
        except Exception as e:
            return ExecutedCommandResponse(message=f"❌ {e}", is_final=True)

    @command(
        Command(name="skip", description="Пропустить трек", tag="skip", permission="sound_core.skip")
    )
    async def handle_skip(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        await self.player.skip_track(command.guild.id)
        return ExecutedCommandResponse(message="⏭️ Пропущено", is_final=True)