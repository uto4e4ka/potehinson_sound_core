from potehinson_sound_core import core
from potehinsonnet.net_models.discord_models import VoiceChannelUserConnectionEvent

from potehinson_sound_core.core import Core
from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import InteractionType
class UserInteraction:
    def __init__(self,core:Core,nats_client:NatsClient):
        self.core = core
        self.nats_client = nats_client
    async def start(self):
        await self.nats_client.subscribe("discord.interaction.channel.voice.event.user.connection",self.on_connect_event)

    async def on_connect_event(self,body:dict):
        event = VoiceChannelUserConnectionEvent.model_validate(body)
        connection = await self.core.get_connection(event.guild.id)
        if connection.playing:
            return
        if event.user.is_bot:
            return
        if event.action != InteractionType.DISCONNECT:
            async def on_ended():
                await self.core.connect(event.after_channel.id,event.guild.id,InteractionType.DISCONNECT)
            await self.core.play_sound("http://ice1.somafm.com/groovesalad-128-mp3",event.after_channel.id,event.guild.id,on_ended)
            print(f"▶️ Playing music for {event.user.name} ({event.user.id}) at server {event.guild.name} ({event.guild.id})")