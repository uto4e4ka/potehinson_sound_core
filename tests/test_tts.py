"""TTS-сервер (FastAPI) и генератор речи edge-tts — без обращения к Microsoft."""
import io

import edge_tts
import pytest
from edge_tts.exceptions import NoAudioReceived
from fastapi.testclient import TestClient
from PIL import Image

from potehinson_sound_core.music import embeds as music_embeds
from potehinson_sound_core.tts.generator import TTSService
from potehinson_sound_core.tts.server import create_app

pytestmark = pytest.mark.usefixtures("fast_sleep")


class FakeTTS:
    def __init__(self, failures: int = 0):
        self.failures = failures
        self.calls = []

    async def generate_stream(self, text, voice, rate, pitch):
        self.calls.append((text, voice, rate, pitch))
        if len(self.calls) <= self.failures:
            raise NoAudioReceived("пусто")
        yield b"ID3"
        yield text.encode()


def test_tts_endpoint_streams_audio():
    service = FakeTTS()
    client = TestClient(create_app(service))

    response = client.get("/integrations/tts", params={"text": "привет & пока", "rate": "+10%"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"ID3" + "привет & пока".encode()
    assert service.calls == [("привет & пока", "ru-RU-DmitryNeural", "+10%", "+0Hz")]


def test_tts_endpoint_retries_failed_generation():
    service = FakeTTS(failures=2)

    response = TestClient(create_app(service)).get("/integrations/tts", params={"text": "hi"})

    assert response.content == b"ID3hi"
    assert len(service.calls) == 3


def test_tts_endpoint_validates_text():
    client = TestClient(create_app(FakeTTS()))

    assert client.get("/integrations/tts").status_code == 422
    assert client.get("/integrations/tts", params={"text": ""}).status_code == 422
    assert client.get("/integrations/tts", params={"text": "x" * 2001}).status_code == 422


def test_tts_head_for_bot_validation():
    # Бот проверяет ссылку HEAD-запросом перед воспроизведением
    assert TestClient(create_app(FakeTTS())).head("/integrations/tts").status_code == 200


class FakeCommunicate:
    chunks: list[dict] = []

    def __init__(self, text, voice, rate, pitch):
        self.args = (text, voice, rate, pitch)

    async def stream(self):
        for chunk in self.chunks:
            yield chunk


async def collect(gen):
    return [chunk async for chunk in gen]


async def test_generator_yields_only_audio(monkeypatch):
    FakeCommunicate.chunks = [{"type": "WordBoundary"}, {"type": "audio", "data": b"a"}, {"type": "audio", "data": b"b"}]
    monkeypatch.setattr(edge_tts, "Communicate", FakeCommunicate)

    assert await collect(TTSService().generate_stream("t", "v", "+0%", "+0Hz")) == [b"a", b"b"]


async def test_generator_without_audio_raises(monkeypatch):
    FakeCommunicate.chunks = [{"type": "WordBoundary"}]
    monkeypatch.setattr(edge_tts, "Communicate", FakeCommunicate)

    with pytest.raises(NoAudioReceived):
        await collect(TTSService().generate_stream("t", "v", "+0%", "+0Hz"))


async def test_dominant_color_from_cover(monkeypatch):
    image = io.BytesIO()
    Image.new("RGB", (20, 20), (200, 10, 10)).save(image, format="PNG")

    class Response:
        status = 200

        async def read(self):
            return image.getvalue()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            pass

    class Session:
        def get(self, url, timeout):
            return Response()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            pass

    monkeypatch.setattr(music_embeds.aiohttp, "ClientSession", Session)

    color = await music_embeds.extract_dominant_color("https://img/red.png")

    r, g, b = color >> 16, (color >> 8) & 0xFF, color & 0xFF
    assert r > 150 and g < 50 and b < 50
