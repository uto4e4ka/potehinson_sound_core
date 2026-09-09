import os

from potehinson_sound_core import core
from potehinsonnet.net_models.discord_models import VoiceChannelUserConnectionEvent, VoiceChannelUserConnectionType

from potehinson_sound_core.core import Core
from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import InteractionType

from scenaries.greeting_repository import GreetingRepository, GreetingScenario


class UserInteraction:
    def __init__(self,core:Core,nats_client:NatsClient,is_greeting:bool,greeting_sound:str,greeting_repository:GreetingRepository):
        self.core = core
        self.nats_client = nats_client
        self.sub = None
        self.is_greeting = is_greeting
        self.greeting_sound = greeting_sound
        self.greeting_repository = greeting_repository

    async def start(self):
        self.greeting_repository.set_greeting(
            GreetingScenario(
                user_id=2,
                guild_id=1,
                sound_url="test"
            )
        )
        print(self.greeting_repository.get_greeting(user_id=2,guild_id=1))
        self.sub = await self.nats_client.subscribe("discord.interaction.channel.voice.event.user.connection",self.on_connect_event)


    async def stop(self):
        await self.sub.unsubscribe()

    async def on_connect_event(self,body:dict):
        event = VoiceChannelUserConnectionEvent.model_validate(body)
        connection = await self.core.get_connection(event.guild.id)
        if event.user.is_bot:
            return
        if connection.playing:
            return
        greeting = self.greeting_repository.get_greeting(
            user_id= event.user.id,
            guild_id=event.guild.id,
        )
        if  greeting.disabled:
            return


        if event.action != VoiceChannelUserConnectionType.DISCONNECTED:
            if not self.is_greeting:
                return
            async def on_ended():
                await self.core.connect(event.after_channel.id,event.guild.id,InteractionType.DISCONNECT)
            await self.core.play_sound(greeting.sound_url,event.after_channel.id,event.guild.id,on_ended)
            print(f"▶️ Playing music for {event.user.name} ({event.user.id}) at server {event.guild.name} ({event.guild.id})")