from typing import Any

from potehinsonnet.net_models.discord_models import ExecutedCommand, ExecutedCommandResponse, Command, CommandArgument

from potehinson_sound_core.core import Core
from potehinsonnet.setup.command_registrator import command

class TTSCommands:
    def __init__(self, core: Core):
        self.core = core

    # @command(
    #     Command(
    #         name="say",
    #         tag="say",
    #         description="Сказать",
    #         permission="sound_core.tts.say",
    #         args=[
    #             CommandArgument(
    #              name="text",
    #             description="Текст"
    #             )
    #         ]
    #     )
    # )
    # async def say(self,command:ExecutedCommand)->ExecutedCommandResponse:
    #     text = next((a.value for a in command.args if a.name == "text"), "")
    #     await self.core.check_and_connect(command.user.voice_channel.id,command.guild.id,force=False)
    #     await self.core.play_sound(
    #         url=f"http://localhost:8000/integrations/tts?text={text}&voice=ru-RU-DmitryNeural",
    #         guild_id=command.guild.id,
    #     )
    #     return ExecutedCommandResponse(
    #         message="▶️ Начинаю говорить", is_final=True
    #     )