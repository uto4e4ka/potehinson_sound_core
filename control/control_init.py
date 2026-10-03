from potehinsonnet.setup.button_registrator import ButtonRegistrator

from control.button_control import ButtonControl
from integrations.tts.edge_tts_generator import logger


class ControlInit:
    def __init__(self,button_registrator:ButtonRegistrator) -> None:
        self.button_registrator=button_registrator

    async def __aenter__(self):
        logger.info("Button Control Init")
        await self.button_registrator.register_instance(ButtonControl())