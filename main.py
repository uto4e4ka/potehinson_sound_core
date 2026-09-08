import asyncio
from typing import cast, Awaitable

from potehinsonnet.net_models.discord_models import Command

from containers.SoundCoreContainer import SoundCoreContainer
from importlib.metadata import version
from dotenv import load_dotenv
load_dotenv()


async def main():

    sound_core_container = SoundCoreContainer()
    sound_core_container.config.plugin.name.from_value("potehinson_sound_core")
    sound_core_container.config.plugin.label.from_value("[🔊] Potehinson Sound Core ")
    sound_core_container.config.plugin.type.from_value("plugin")
    sound_core_container.config.plugin.description.from_value("Воспроизведение, управление звуками.\nПриветствие и ивенты.")
    sound_core_container.config.plugin.icon.from_value("")
    sound_core_container.config.plugin.author.from_value("Uto4ka404")
    sound_core_container.config.plugin.version.from_value(
        "0.0.1"
    )
    sound_core_container.config.plugin.site.from_value("https://potehinson-sound-core")
    sound_core_container.config.is_greeting.from_env("GREETING")
    sound_core_container.config.greeting_sound.from_env("GREETING_SOUND")
    await sound_core_container.init_resources()

    try:
        await asyncio.Event().wait()
    finally:
        print("Shutting down")
        await sound_core_container.shutdown_resources()




asyncio.run(main())