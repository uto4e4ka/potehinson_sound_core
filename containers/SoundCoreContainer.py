from contextlib import asynccontextmanager, _AsyncGeneratorContextManager
from typing import AsyncGenerator

from dependency_injector import containers,providers
from dependency_injector.providers import Singleton
from potehinsonnet.containers.nats_container import NatsContainer
from potehinsonnet.monitoring.health import Health
from potehinsonnet.net import NatsClient
from potehinsonnet.steup import command_registrator

from potehinson_sound_core.command_installer import CommandInstaller
from potehinson_sound_core.core import Core
from potehinson_sound_core.user_interaction import UserInteraction


@asynccontextmanager
async def _init_user_interaction(
        core: Core,
        nats_client: NatsClient,
        is_greeting: bool,
        greeting_sound: str
) -> AsyncGenerator[UserInteraction, None]:
    interaction = UserInteraction(core, nats_client, is_greeting, greeting_sound)
    await interaction.start()
    try:
        yield interaction
    finally:
        await interaction.stop()

async def _init_command_registrator(
        command_registrator: command_registrator.CommandRegistrator,
        core:Core,
        health:Health,
) -> AsyncGenerator[CommandInstaller, None]:
    installer = CommandInstaller(command_registrator,core)
    await health.add_listener(installer.start)

    try:
        yield installer
    finally:
        await installer.stop()

class SoundCoreContainer(containers.DeclarativeContainer):
    config = providers.Configuration(
        default={
            "nats": {
                "url": "nats://localhost:4222",
            }
        }
    )
    nats_container: providers.Container = providers.Container(NatsContainer,config = config)
    core: Singleton[Core] = providers.Singleton(Core,nats_client = nats_container.nats)
    user_interaction: providers.Resource[UserInteraction|_AsyncGeneratorContextManager[UserInteraction,None]] = providers.Resource(_init_user_interaction,
                                                                               core=core,
                                                                               nats_client=nats_container.nats,
                                                                               is_greeting=config.is_greeting,
                                                                               greeting_sound=config.greeting_sound
                                                                               )
    command_registrator:providers.Resource[CommandInstaller]= providers.Resource(_init_command_registrator,
                                                                                 command_registrator = nats_container.command_registrator,
                                                                                 core=core,
                                                                                 health = nats_container.health,
                                                                                 )