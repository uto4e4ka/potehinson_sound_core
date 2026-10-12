"""MusicFetcher, retry, TTS-резолвер и разбор ссылок Яндекс Музыки."""
import time
from types import SimpleNamespace

import pytest

from integrations.music.music_embeds import AddingType
from integrations.music.music_fetcher import MusicFetcher
from integrations.music.music_models import MusicSource
from integrations.music.radios.yandex.utils import get_formatted_track_id, get_played_time, get_time
from integrations.music.resolvers.resolver import BaseResolver
from integrations.music.resolvers.tts.tts_resolver import TtsResolver
from integrations.music.resolvers.yandex.utils import _get_artists_str, _parse_url, get_track_page_url
from potehinson_sound_core.utils import retry
from tests.conftest import track

pytestmark = pytest.mark.usefixtures("fast_sleep")


class FlakyResolver(BaseResolver):
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def find_musics(self, url):
        return f"found {url}"

    async def get_track_by_url(self, url):
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError("сеть")
        return track(url)

    def can_resolve(self, url):
        return url.startswith("flaky:")


async def test_fetcher_picks_matching_resolver():
    fetcher = MusicFetcher([TtsResolver(), FlakyResolver(0)])

    assert await fetcher.get_musics("flaky:x") == "found flaky:x"
    tts = await fetcher.get_music_by_url("http://localhost:8000/integrations/tts?text=a")
    assert tts.source is MusicSource.POTEHINSON_TTS


async def test_fetcher_rejects_unknown_links():
    with pytest.raises(FileNotFoundError, match="не поддерживается"):
        await MusicFetcher([TtsResolver()]).get_musics("https://unknown.site/track")


async def test_fetcher_retries_flaky_resolver():
    resolver = FlakyResolver(failures=2)

    result = await MusicFetcher([resolver]).get_music_by_url("flaky:a")

    assert result.music.name == "flaky:a"
    assert resolver.calls == 3


async def test_retry_gives_up_after_count():
    calls = []

    @retry(3, 1)
    async def always_fails():
        calls.append(1)
        raise ValueError("нет")

    with pytest.raises(ValueError):
        await always_fails()
    assert len(calls) == 3


async def test_tts_resolver():
    resolver = TtsResolver()
    url = "http://localhost:8000/integrations/tts?text=привет"

    found = await resolver.find_musics(url)

    assert resolver.can_resolve(url) and not resolver.can_resolve("https://music.yandex.ru/track/1")
    assert found.add_type is AddingType.SAY
    assert found.music_list[0].music.url == url
    assert (await resolver.get_track_by_url(url)).music.track_url == url


@pytest.mark.parametrize("url, expected", [
    ("https://music.yandex.ru/album/5/track/123", {"type": AddingType.TRACK, "track_id": "123"}),
    ("https://music.yandex.ru/track/123?utm=x", {"type": AddingType.TRACK, "track_id": "123"}),
    ("https://music.yandex.ru/album/5", {"type": AddingType.ALBUM, "album_id": "5"}),
    ("https://music.yandex.ru/users/vasya/playlists/1003", {"type": AddingType.PLAYLIST, "user_id": "vasya", "playlist_id": "1003"}),
    ("https://music.yandex.ru/playlists/lk.abc-def", {"type": AddingType.PLAYLIST, "user_id": None, "playlist_id": "lk.abc-def"}),
    ("https://music.yandex.ru/artist/77", {"type": AddingType.AUTHOR, "user_id": "77"}),
    ("yandex_wave:42", {"type": AddingType.WAVE, "track_id": "42"}),
    ("кино группа крови", {"type": AddingType.SEARCH, "track_id": "кино группа крови"}),
])
def test_parse_yandex_url(url, expected):
    link = _parse_url(url)

    assert {k: getattr(link, k) for k in expected} == expected


def test_artists_and_page_url():
    artists = [SimpleNamespace(name="A"), SimpleNamespace(name=None), SimpleNamespace(name="B")]

    assert _get_artists_str(artists) == "A, B"
    assert _get_artists_str([]) == "Unknown"
    assert get_track_page_url(5, 123) == "https://music.yandex.ru/album/5/track/123"


def test_radio_helpers():
    with_real_id = SimpleNamespace(id="1", real_id="9", albums=[SimpleNamespace(id=5)])
    no_album = SimpleNamespace(id="1", albums=[])

    assert get_formatted_track_id(with_real_id) == "9:5"
    assert get_formatted_track_id(no_album) == "1:0"
    assert get_played_time(0) == 0.0
    assert 4.9 < get_played_time(time.time() - 5) < 5.5
    assert get_time().endswith("Z") and len(get_time()) == 24
