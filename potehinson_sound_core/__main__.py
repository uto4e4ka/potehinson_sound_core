import asyncio

from dotenv import load_dotenv

from potehinson_sound_core.app import create_plugin
from potehinson_sound_core.settings import Settings
from potehinson_sound_core.tts.generator import TTSService
from potehinson_sound_core.tts.server import create_app, run_tts_server


async def main() -> None:
    load_dotenv()
    settings = Settings.from_env()

    plugin = create_plugin(settings)
    plugin.add_lifespan(run_tts_server(create_app(TTSService()), host=settings.tts_host, port=settings.tts_port))
    await plugin.serve()


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
