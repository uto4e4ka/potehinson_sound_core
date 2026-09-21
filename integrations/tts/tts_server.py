from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from integrations.edge_tts_generator import TTSService


def create_app(tts_service: TTSService) -> FastAPI:
    app = FastAPI(title="Edge TTS Streaming Proxy")

    @app.head("/tts")
    async def tts_head():
        return {
            "status": "ok"
        }

    @app.get("/tts")
    async def tts_endpoint(
        text: str = Query(..., min_length=1, max_length=2000),
        voice: str = Query("ru-RU-DmitryNeural"),
        rate: str = Query("+0%"),
        pitch: str = Query("+0Hz"),
    ):
        try:
            return StreamingResponse(
                tts_service.generate_stream(text, voice, rate, pitch),
                media_type="audio/mpeg",
                headers={"Content-Disposition": "inline; filename=speech.mp3"},
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Ошибка генерации TTS: {str(e)}"
            )

    return app
