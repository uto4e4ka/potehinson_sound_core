import logging
import edge_tts
from edge_tts.exceptions import NoAudioReceived

logger = logging.getLogger(__name__)


class TTSService:
    async def generate_stream(self, text: str, voice: str, rate: str, pitch: str):
        communicator = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)

        has_audio = False
        try:
            async for chunk in communicator.stream():
                if chunk["type"] == "audio":
                    has_audio = True
                    yield chunk["data"]

            if not has_audio:
                raise NoAudioReceived("Аудиопоток пуст. Проверьте голос и параметры.")

        except NoAudioReceived as e:
            logger.error(f"Edge TTS NoAudioReceived: {e}")
            raise
        except Exception as e:
            logger.exception(f"Ошибка при передаче аудиопотока: {e}")
            raise