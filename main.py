import asyncio
from typing import cast, Awaitable

from potehinsonnet.net_models.discord_models import Command

from containers.SoundCoreContainer import SoundCoreContainer
from potehinsonnet.steup.command_registrator import CommandRegistrator
from dotenv import load_dotenv
load_dotenv()


async def main():

    sound_core_container = SoundCoreContainer()
    sound_core_container.config.plugin.name.from_value("potehinson_sound_core")
    sound_core_container.config.plugin.label.from_value("potehinson_discord_core")
    sound_core_container.config.is_greeting.from_env("GREETING")
    sound_core_container.config.greeting_sound.from_env("GREETING_SOUND")
    await sound_core_container.init_resources()





    await asyncio.Event().wait()
asyncio.run(main())