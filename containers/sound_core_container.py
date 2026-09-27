from contextlib import asynccontextmanager, _AsyncGeneratorContextManager
from typing import AsyncGenerator

from dependency_injector import containers, providers
from dependency_injector.providers import Singleton
from fastapi import FastAPI
from potehinsonnet import discord_provider
from potehinsonnet.containers.nats_container import NatsContainer
from potehinsonnet.monitoring.health import Health
from potehinsonnet.net import NatsClient
from potehinsonnet.setup import command_registrator

from integrations.music.music_fetcher import MusicFetcher
from integrations.music.resolvers.yandex.yandex_resolver import YandexResolver
from integrations.tts.edge_tts_generator import TTSService
from integrations.tts.tts_server import create_app
from potehinson_sound_core.command_installer import CommandInstaller
from potehinson_sound_core.core import Core
from potehinson_sound_core.music_player import MusicPlayer
from potehinson_sound_core.user_interaction import UserInteraction
from scenaries.greeting_repository import GreetingRepository


@asynccontextmanager
async def _init_user_interaction(
        core: Core,
        nats_client: NatsClient,
        is_greeting: bool,
        greeting_sound: str,
        greeting_repository: GreetingRepository,
) -> AsyncGenerator[UserInteraction, None]:
    interaction = UserInteraction(core, nats_client, is_greeting, greeting_sound, greeting_repository)
    await interaction.start()
    try:
        yield interaction
    finally:
        await interaction.stop()


async def _init_command_registrator(
        command_registrator: command_registrator.CommandRegistrator,
        core: Core,
        health: Health,
        discord_provider: discord_provider.DiscordProvider,
        greeting_repository: GreetingRepository,
        music_player: MusicPlayer,
) -> AsyncGenerator[CommandInstaller, None]:
    installer = CommandInstaller(command_registrator, core, discord_provider, greeting_repository,music_player)
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
            },
            "greeting_repository": {
                "json_path": "../data/scenaries/greeting.json",
            },
            "yandex_token": None,  # Добавлен ключ по умолчанию
        }
    )

    nats_container: providers.Container = providers.Container(NatsContainer, config=config)
    core: Singleton[Core] = providers.Singleton(Core, nats_client=nats_container.nats)

    greeting_repository: Singleton[GreetingRepository] = providers.Singleton(  # Добавлен пропущенный `providers.`
        GreetingRepository,
        json_path=config.greeting_repository.json_path,
    )

    user_interaction: providers.Resource[
        UserInteraction | _AsyncGeneratorContextManager[UserInteraction, None]] = providers.Resource(
        _init_user_interaction,
        core=core,
        nats_client=nats_container.nats,
        is_greeting=config.is_greeting,
        greeting_sound=config.greeting_sound,
        greeting_repository=greeting_repository
    )

    # Токен берется из скорректированного пути конфига
    yandex_resolver: Singleton[YandexResolver] = providers.Singleton(
        YandexResolver,
        token=config.integrations.music.resolvers.yandex_token
    )

    # Убрано присвоение типа `: providers.List` (в dependency_injector это класс-фабрика)
    resolvers = providers.List(
        yandex_resolver
    )

    music_fetcher: Singleton[MusicFetcher] = providers.Singleton(
        MusicFetcher,
        resolvers=resolvers
    )

    music_player: Singleton[MusicPlayer] = providers.Singleton(MusicPlayer,core=core,music_fetcher=music_fetcher)

    command_registrator: providers.Resource[CommandInstaller] = providers.Resource(
        _init_command_registrator,
        command_registrator=nats_container.command_registrator,
        core=core,
        health=nats_container.health,
        discord_provider=nats_container.discord_provider,
        greeting_repository=greeting_repository,
        music_player = music_player,
    )

    tts_service: Singleton[TTSService] = providers.Singleton(TTSService)

    app: providers.Factory[FastAPI] = providers.Factory(
        create_app,
        tts_service=tts_service,
    )