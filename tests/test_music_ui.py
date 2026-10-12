"""Модели музыки, эмбеды и карточка "Сейчас играет"."""
import pytest
from potehinsonnet.net_models.discord_models import ActionRow, ComponentThumbnail, Section, TextDisplay

from integrations.music.music_components import get_music_container
from integrations.music.music_embeds import (
    AddingType,
    MusicAddMessage,
    extract_dominant_color,
    format_duration,
    get_add_embed,
    get_music_embed,
)
from integrations.music.music_models import AudioQuality, MusicSource, PlayingType
from integrations.music.resolvers.tts.tts_resolver import TtsResolver
from tests.conftest import track


@pytest.mark.parametrize("bitrate, quality", [
    (0, AudioQuality.LOW), (None, AudioQuality.LOW), (128, AudioQuality.LOW),
    (192, AudioQuality.MEDIUM), (250, AudioQuality.HIGH), (320, AudioQuality.VERY_HIGH), (1000, AudioQuality.VERY_HIGH),
])
def test_quality_from_bitrate(bitrate, quality):
    assert AudioQuality.from_bitrate(bitrate) is quality


def test_quality_names():
    assert [q.display_name for q in AudioQuality] == ["LQ", "SQ", "HQ", "HQ+"]


@pytest.mark.parametrize("seconds, text", [(0, "`0` мин `00` сек"), (65.9, "`1` мин `05` сек"), (3600, "`60` мин `00` сек")])
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


async def test_music_feedback_is_safe():
    calls = []

    async def feedback(event, seconds):
        calls.append((event, seconds))
        raise RuntimeError("API недоступно")

    music = track("a").music
    music.feedback_callback = feedback

    await music.send_feedback("skip", 12.5)
    await track("b").music.send_feedback("skip")   # без колбэка — ничего не делает

    assert calls == [("skip", 12.5)]
    assert "feedback_callback" not in music.model_dump()


async def test_no_cover_means_no_color():
    assert await extract_dominant_color("") is None


async def test_unreachable_cover_means_no_color(monkeypatch):
    def offline(*args, **kwargs):
        raise OSError("нет сети")

    monkeypatch.setattr("aiohttp.ClientSession", offline)

    assert await extract_dominant_color("https://img/cover.png") is None


def test_add_embed_without_cover_has_no_thumbnail():
    # Пустой URL картинки Discord отклоняет с 400
    embed = get_add_embed(MusicAddMessage(add_type=AddingType.SAY, source=MusicSource.POTEHINSON_TTS, name="Фраза"))

    assert embed.thumbnail is None
    assert embed.url is None


def test_add_embed_with_cover():
    embed = get_add_embed(MusicAddMessage(
        add_type=AddingType.ALBUM, source=MusicSource.YANDEX_MUSIC, name="Альбом",
        url="https://music/album", icon_url="https://img/a.png", count=12, queue_count=15,
    ))

    assert embed.thumbnail.url == "https://img/a.png"
    assert [f.value for f in embed.fields] == ["12", "15"]
    assert embed.author.name == AddingType.ALBUM


async def test_music_embed(monkeypatch):
    monkeypatch.setattr("integrations.music.music_embeds.extract_dominant_color", _no_color)
    embed = await get_music_embed(track("a"))

    assert embed.color == 0xFF69B4
    assert embed.footer.text == "YandexMusic • HQ"


async def _no_color(url):
    return None


@pytest.fixture(autouse=True)
def no_network_colors(monkeypatch):
    async def color(url):
        return 0x112233 if url else None

    monkeypatch.setattr("integrations.music.music_components.extract_dominant_color", color)


async def test_card_with_cover_uses_section_with_thumbnail():
    container = await get_music_container(track("Song"))

    header = container.components[0]
    assert isinstance(header, Section)
    assert isinstance(header.accessory, ComponentThumbnail)
    assert "### [Song](https://music/Song)" in header.content
    assert container.accent_color == 0x112233


async def test_tts_card_has_no_thumbnail():
    # Это был 400 Bad Request при /say
    tts = await TtsResolver().get_track_by_url("http://localhost:8000/integrations/tts?text=hi")

    container = await get_music_container(tts)

    header = container.components[0]
    assert isinstance(header, TextDisplay)
    assert header.content == f"{PlayingType.SPEECH.value}\n### Phrase TTS\nPotehinson\n"
    assert container.accent_color is None


async def test_card_buttons_and_shuffle_icon():
    plain = await get_music_container(track("a"))
    shuffled = await get_music_container(track("a"), shuffle=True)

    rows = [c for c in plain.components if isinstance(c, ActionRow)]
    ids = [b.custom_id for row in rows for b in row.components]
    assert ids == ["music:shuffle", "music:stop", "music:prev", "music:pause", "music:skip", "music:wave_from_track"]
    assert rows[1].components[3].context == {"track_id": "a"}
    assert rows[0].components[0].label == "🔀"
    assert [c for c in shuffled.components if isinstance(c, ActionRow)][0].components[0].label == "↔️"
