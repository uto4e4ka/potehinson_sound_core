import asyncio
from typing import Awaitable, Callable
from urllib import response

from potehinsonnet.net_models.discord_models import VoiceChannelUserConnectionEvent, VoiceChannelConnectInteraction, \
    Channel, Guild, VoicePlayingCallback
from potehinsonnet.net_models.discord_models import InteractionType, VoiceChannelPlaySound,VoiceChannelUserConnectionType,VoiceConnectionStatus,VoiceConnectionRequest
from potehinsonnet.net import NatsClient
import uuid

from exeptions.playing_execptions import PlayingException

CONNECTED = VoiceChannelUserConnectionType.CONNECTED
DISCONNECTED = VoiceChannelUserConnectionType.DISCONNECTED
MOVE = VoiceChannelUserConnectionType.MOVE


class Core:
    def __init__(self,nats_client:NatsClient):
        self.nats_client = nats_client
        self.bot_state = DISCONNECTED
        self.bot_connected = asyncio.Event()

    async def get_connection(self,guild_id:int)->VoiceConnectionStatus:
        status = await self.nats_client.request("discord.interaction.channel.voice.connection.status", {
        "guild_id": guild_id,
    } ,timeout=10)
        return VoiceConnectionStatus.model_validate(status)

    async def connect(self,channel_id:int,guild_id:int,interraction_type:InteractionType = InteractionType.CONNECT)-> VoiceConnectionStatus:
        status = await self.nats_client.request("discord.interaction.channel.voice.actions.connect",VoiceConnectionRequest(
            channel=Channel(id= channel_id,name=""),
            guild = Guild(id= guild_id,name=""),
            interaction_type= interraction_type
        ).model_dump(mode="json"))
        return VoiceConnectionStatus.model_validate(status)

    async def play_sound(self,
                url:str,
                channel_id:int,
                guild_id:int,
                on_ended: Callable[[], Awaitable[None]] | None = None
                         ):
        track_id = str(uuid.uuid4())
        status = await self.get_connection(guild_id)
        if not status.connected or status.channel.id != channel_id:
            await self.connect(channel_id,guild_id)
        response = await self.nats_client.request(
            "discord.interaction.channel.voice.actions.play_sound",
            VoiceChannelPlaySound(
                sound=url,
                track_id=track_id,
                channel = Channel(id= channel_id,name=""),
                guild = Guild(id= guild_id,name="")
            ).model_dump(mode="json"))
        response = VoicePlayingCallback.model_validate(response)
        if not response.success:
            raise PlayingException(response.message)
        if on_ended:
            async def _on_sound_ended_msg(msg):
                    await on_ended()
                    await sub.unsubscribe()

            sub = await self.nats_client.subscribe(
                f"discord.interaction.channel.voice.events.sound_ended.{track_id}",
                _on_sound_ended_msg
            )








