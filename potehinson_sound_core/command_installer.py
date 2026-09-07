from potehinsonnet.net_models.discord_models import Command, CommandArgument, ExecutedCommand
from potehinsonnet.steup.command_registrator import CommandRegistrator

from potehinson_sound_core.core import Core


class CommandInstaller:
    def __init__(self,command_registrator:CommandRegistrator,core:Core):
        self.command_registrator = command_registrator
        self.core = core

    async def start(self) -> None:
        async def command_callback(body: dict) -> None:
            command = ExecutedCommand.model_validate(body)
            print(body)
            await self.core.play_sound(url = command.args[1].value,

                                      channel_id=int(command.args[0].value),
                                       guild_id=command.guild.id,
                                       )
            return

        await self.command_registrator.register_command(
            Command(name="play_channel",
                    description="Проиграть в канале",
                    tag="play",
                    service=self.command_registrator.plugin_name,
                    args=[CommandArgument(
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
                        )
                    ]
                    ),
            command_callback
        )
    async def stop(self) -> None:
        return