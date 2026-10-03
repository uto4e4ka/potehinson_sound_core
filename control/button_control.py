from loguru import logger
from potehinsonnet.net_models.discord_models import ExecutedComponent, ExecutedComponentResponse
from potehinsonnet.setup.button_registrator import button, ButtonRegistrator
from werkzeug.exceptions import NotFound

from integrations.music.clients.yandex_client import YandexClientRepo
from integrations.music.player import music_player
from integrations.music.player.music_player import MusicPlayer
from integrations.music.player.providers.queue_stream_provider import QueueStreamProvider
from integrations.music.player.providers.radio_stream_provider import RadioStreamProvider
from integrations.music.radios.radio import BaseRadio
from integrations.music.radios.yandex.yandex_radio import YandexWave



class ButtonControl:
    def __init__(self,music_player:MusicPlayer,yandex_repo:YandexClientRepo):
        self.music_player = music_player
        self.yandex_repo = yandex_repo

    @button("music:pause")
    async def pause(self,arg:ExecutedComponent):
        guild_id = arg.guild.id
        await self.music_player.pause_track(guild_id)

    @button("music:skip")
    async def skip(self,arg:ExecutedComponent):
        guild_id = arg.guild.id
        await self.music_player.skip_track(guild_id)
        print(arg.context)

    @button("music:prev")
    async def prev(self,arg:ExecutedComponent):
        guild_id = arg.guild.id
        await self.music_player.previous_track(guild_id)

    @button("music:wave_from_track")
    async def wave_by_track(self,arg:ExecutedComponent):
        id = arg.context["track_id"]
        if not id:
            logger.warning("No context by track_id")
            raise NotFound("Ну удается запустить волну по треку.")
        client = await self.yandex_repo.get_async_music_client(arg.user.id)
        radio = YandexWave(client)
        await radio.init("track", f"{id}")
        provider = RadioStreamProvider(radio)
        self.music_player.set_provider(arg.guild.id,provider)
        logger.info(f"Волна по треку {id}")
        return ExecutedComponentResponse(message=f"🌊Запускаю волну по треку",ephemeral=True)

    @button("music:shuffle")
    async def shuffle(self,arg:ExecutedComponent):
        guild_id = arg.guild.id
        provider = self.music_player.providers.get(guild_id)
        if not provider:
            raise FileNotFoundError("Не доступно в этом режиме.")
        if not hasattr(provider, "shuffle_queue"):
            raise FileNotFoundError("Не доступно в этом режиме.")

        is_shuffled = provider.shuffle_queue()

        return ExecutedComponentResponse(
            message=(
                "🔀 Случайное воспроизведение включено"
                if is_shuffled
                else "➡️ Случайное воспроизведение отключено"
            ),
            is_finish=True,
            ephemeral=True
        )

    @button("music:stop")
    async def stop(self,arg:ExecutedComponent):
        guild_id = arg.guild.id
        await self.music_player.stop_player(guild_id)



