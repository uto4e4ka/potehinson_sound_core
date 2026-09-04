import asyncio

from potehinsonnet.monitoring.health import Health
from potehinsonnet.monitoring.health import NatsClient

from potehinson_sound_core import user_interaction
from potehinson_sound_core.core import Core
from potehinson_sound_core.user_interaction import UserInteraction
async def main():
    nats_client = NatsClient()
    await nats_client.connect()
    health = Health(nats_client,"potehinson_sound_core")
    core = Core(nats_client)
    user_interaction = UserInteraction(core,nats_client)
    await user_interaction.start()
    await asyncio.Event().wait()
asyncio.run(main())