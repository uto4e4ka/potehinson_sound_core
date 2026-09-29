import asyncio
import logging
from functools import wraps

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from edge_tts.exceptions import NoAudioReceived

from integrations.tts.edge_tts_generator import TTSService

logger = logging.getLogger(__name__)


def create_app(tts_service: TTSService) -> FastAPI:
    app = FastAPI(title="Edge TTS Streaming Proxy")

    @app.head("/integrations/tts")
    async def tts_head():
        return {"status": "ok"}

    async def safe_stream_wrapper(text: str, voice: str, rate: str, pitch: str, max_retries: int = 3, delay: float = 1.0):
        """
        Обертка над генератором с повторными попытками (retry) 
        прямо во время стриминга.
        """
        for attempt in range(1, max_retries + 1):
            try:
                async for chunk in tts_service.generate_stream(text, voice, rate, pitch):
                    yield chunk
                # Если генерация успешно завершилась — выходим
                return
            except (NoAudioReceived, Exception) as e:
                logger.warning(f"Попытка TTS {attempt}/{max_retries} завершилась ошибкой: {e}")
                if attempt == max_retries:
                    logger.error("Все попытки генерации TTS исчерпаны.")
                    raise

                await asyncio.sleep(delay)

    @app.get("/integrations/tts")
    async def tts_endpoint(
        text: str = Query(..., min_length=1, max_length=2000),
        voice: str = Query("ru-RU-DmitryNeural"),
        rate: str = Query("+0%"),
        pitch: str = Query("+0Hz"),
    ):
        print(f"Запрос TTS: text='{text}', voice='{voice}', rate='{rate}', pitch='{pitch}'")

        # Передаем управляемый асинхронный генератор в StreamingResponse
        return StreamingResponse(
            safe_stream_wrapper(text, voice, rate, pitch, max_retries=3, delay=1.0),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )

    return app