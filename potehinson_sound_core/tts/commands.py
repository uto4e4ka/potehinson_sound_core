from typing import Any
from urllib.parse import urlencode

from potehinsonnet.net_models.discord_models import ExecutedCommand, ExecutedCommandResponse, Command, CommandArgument

from potehinson_sound_core.exceptions import PlayingException
from potehinson_sound_core.music.fetcher import MusicFetcher
from potehinson_sound_core.music.player.player import MusicPlayer
from potehinson_sound_core.music.player.queue import QueueStreamProvider
from potehinson_sound_core.core import Core
from potehinsonnet.setup.command_registrator import command

class TTSCommands:
    def __init__(self,music_fetcher: MusicFetcher,player:MusicPlayer) -> None:
        self.music_fetcher = music_fetcher
        self.player = player


    def get_provider(self,guild_id:int):
        return self.player.get_or_create_provider(guild_id,QueueStreamProvider,music_fetcher=self.music_fetcher)

    def _ensure_voice(self, command: ExecutedCommand) -> int:
        if not command.user or not command.user.voice_channel:
            raise PlayingException("Нужно находиться в голосовом канале")
        return command.user.voice_channel.id

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

            provider = self.get_provider(guild_id)
            # Текст экранируем, иначе "&", "#" или "?" во фразе ломают ссылку
            query = urlencode({"text": text, "voice": "ru-RU-DmitryNeural"})
            await provider.add_music(f"http://localhost:8000/integrations/tts?{query}")
            await self.player.add_to_channel_player(
                channel_id, guild_id, command.channel.id
            )
            return ExecutedCommandResponse(message="🗣️ Начинаю говорить", is_final=True)
        except Exception as e:
            return ExecutedCommandResponse(message=f"❌ {e}", is_final=True)