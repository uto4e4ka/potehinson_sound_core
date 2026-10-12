import asyncio

from dotenv import load_dotenv

from integrations.tts.edge_tts_generator import TTSService
from integrations.tts.tts_server import create_app, run_tts_server
from potehinson_sound_core.app import Settings, create_plugin


async def main() -> None:
    load_dotenv()
    settings = Settings.from_env()

    plugin = create_plugin(settings)
    plugin.add_lifespan(run_tts_server(create_app(TTSService()), host=settings.tts_host, port=settings.tts_port))
    await plugin.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
