import edge_tts
from typing import AsyncGenerator

class TTSService:
    async def generate_stream(
        self, text: str, voice: str, rate: str, pitch: str
    ) -> AsyncGenerator[bytes, None]:
        communicator = edge_tts.Communicate(
            text=text, voice=voice, rate=rate, pitch=pitch
        )
        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]