"""Резолвер Яндекс Музыки и "Моя волна" на фейковом клиенте API (без сети и токена)."""
from types import SimpleNamespace

import pytest

from potehinson_sound_core.music.yandex.client import YandexClientRepo
from potehinson_sound_core.music.embeds import AddingType
from potehinson_sound_core.music.models import AudioQuality, PlayingType
from potehinson_sound_core.music.yandex.wave import YandexWave
from potehinson_sound_core.music.yandex.resolver import YandexResolver

pytestmark = pytest.mark.usefixtures("fast_sleep")


class Info:
    def __init__(self, bitrate):
        self.bitrate_in_kbps = bitrate

    async def get_direct_link_async(self):
        return f"https://cdn/{self.bitrate_in_kbps}.mp3"

    def get_direct_link(self):
        return f"https://cdn/{self.bitrate_in_kbps}.mp3"


class FakeTrack(SimpleNamespace):
    def __init__(self, id, title=None, album=5):
        super().__init__(
            id=id, real_id=id, title=title or f"Track {id}", duration_ms=180_000,
            albums=[SimpleNamespace(id=album, title="Album")] if album else [],
            artists=[SimpleNamespace(name="Кино")],
        )

    def get_cover_url(self, size="200x200"):
        return f"https://img/{self.id}/{size}"

    async def get_download_info_async(self):
        return [Info(128), Info(320), Info(192)]

    def get_download_info(self):
        return [Info(320)]


class FakeClient:
    def __init__(self):
        self.calls = []
        self.batches = 0
        self.feedback = []

    async def tracks(self, ids):
        self.calls.append(("tracks", ids))
        return [FakeTrack(i) for i in ids if i != "404"]

    async def albums_with_tracks(self, album_id):
        return SimpleNamespace(
            title="Группа крови", volumes=[[FakeTrack("1"), FakeTrack("2")], [FakeTrack("3")]],
            get_og_image_url=lambda size: f"https://img/album/{size}",
        )

    async def users_playlists(self, playlist_id, user_id):
        self.calls.append(("users_playlists", playlist_id, user_id))
        return self._playlist()

    async def playlist(self, playlist_id):
        self.calls.append(("playlist", playlist_id))
        return self._playlist()

    def _playlist(self):
        return SimpleNamespace(
            title="Мой плейлист", cover=None,
            tracks=[SimpleNamespace(track=FakeTrack("7")), SimpleNamespace(track=None), SimpleNamespace(track=FakeTrack("8", album=None))],
        )

    async def artists_tracks(self, artist_id, page, page_size):
        start = page * page_size
        return [FakeTrack(str(i)) for i in range(start, min(start + page_size, 45))]

    async def artists(self, ids):
        return [SimpleNamespace(name="Кино", cover=None, get_og_image_url=lambda size: "")]

    async def search(self, query):
        artist = SimpleNamespace(id=77, name="Кино")
        return SimpleNamespace(
            tracks=SimpleNamespace(results=[FakeTrack("99", title=query)]),
            artists=SimpleNamespace(results=[artist]),
        )

    # --- Моя волна ---
    async def rotor_session_new(self, seeds, include_tracks_in_response):
        self.calls.append(("session", seeds))
        return SimpleNamespace(radio_session_id="S1")

    async def rotor_session_clone(self, radio_session_id):
        return SimpleNamespace(radio_session_id=radio_session_id)

    async def rotor_session_feedback_radio_started(self, session_id, from_):
        self.feedback.append("radioStarted")

    async def rotor_session_feedback_track_started(self, session_id, track_id, batch_id, from_):
        self.feedback.append(("trackStarted", track_id))

    async def rotor_session_tracks(self, session_id, queue, feedbacks):
        self.batches += 1
        self.feedback.extend(f.event.type for f in feedbacks or [])
        base = self.batches * 10
        return SimpleNamespace(
            batch_id=f"B{self.batches}",
            sequence=[SimpleNamespace(track=FakeTrack(str(base + i))) for i in range(2)],
        )


class FakeRepo(YandexClientRepo):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.requests = 0

    async def get_async_music_client(self, user_id):
        self.requests += 1
        return self.client


@pytest.fixture
def client():
    return FakeClient()


@pytest.fixture
def resolver(client):
    return YandexResolver(FakeRepo(client))


async def test_track_link(resolver):
    found = await resolver.find_musics("https://music.yandex.ru/album/5/track/123")

    assert found.add_type is AddingType.TRACK
    assert found.music_list[0].music.url == "https://music.yandex.ru/album/5/track/123"
    assert found.music_list[0].music.track_url == "https://cdn/128.mp3"


async def test_album_link(resolver):
    found = await resolver.find_musics("https://music.yandex.ru/album/5")

    assert (found.name, found.count) == ("Группа крови", 3)
    assert found.icon_url == "https://img/album/150x150"


async def test_playlist_links(resolver, client):
    old = await resolver.find_musics("https://music.yandex.ru/users/vasya/playlists/1003")
    new = await resolver.find_musics("https://music.yandex.ru/playlists/lk.3f9c-aa")

    assert ("users_playlists", "1003", "vasya") in client.calls
    assert ("playlist", "lk.3f9c-aa") in client.calls
    # трек без данных пропускается, трек без альбома получает album/0
    assert [m.music.url for m in new.music_list] == [
        "https://music.yandex.ru/album/5/track/7", "https://music.yandex.ru/album/0/track/8",
    ]
    assert old.icon_url == ""


async def test_artist_link_paginates(resolver):
    found = await resolver.find_musics("https://music.yandex.ru/artist/77")

    assert found.count == 45
    assert found.name == "Популярное: Кино"


async def test_search_prefers_exact_artist(resolver):
    found = await resolver.find_musics("кино")

    assert found.add_type is AddingType.AUTHOR


async def test_search_falls_back_to_track(resolver):
    found = await resolver.find_musics("группа крови")

    assert found.add_type is AddingType.TRACK
    assert found.name == "группа крови"


async def test_get_track_by_url_picks_best_quality(resolver):
    attrs = await resolver.get_track_by_url("https://music.yandex.ru/album/5/track/123")

    assert attrs.music.track_url == "https://cdn/320.mp3"
    assert attrs.quality is AudioQuality.VERY_HIGH
    assert attrs.duration == 180
    assert attrs.author.name == "Кино"


@pytest.mark.parametrize("url", ["https://other.site/track/1", "https://music.yandex.ru/album/5", "https://music.yandex.ru/track/404"])
async def test_get_track_by_url_errors(resolver, url):
    with pytest.raises(FileNotFoundError):
        await resolver.get_track_by_url(url)


async def test_get_tracks_by_url(resolver):
    tracks = await resolver.get_tracks_by_url("https://music.yandex.ru/album/5")

    assert [t.music.name for t in tracks] == ["Track 1", "Track 2", "Track 3"]


async def test_resolver_uses_injected_client_repo(resolver):
    # Раньше большинство методов создавали новый YandexClientRepo — без кэша, с новой авторизацией на каждый трек
    await resolver.find_musics("https://music.yandex.ru/album/5/track/1")
    await resolver.get_track_by_url("https://music.yandex.ru/album/5/track/1")

    assert resolver.client_repo.requests == 2


async def test_client_repo_caches_per_user(monkeypatch):
    created = []

    class FakeClientAsync:
        def __init__(self, token):
            created.append(token)

        async def init(self):
            return self

    monkeypatch.setattr("potehinson_sound_core.music.yandex.client.ClientAsync", FakeClientAsync)
    monkeypatch.setenv("YANDEX_TOKEN", "secret")
    repo = YandexClientRepo()

    first = await repo.get_async_music_client(1)

    assert await repo.get_async_music_client(1) is first
    assert created == ["secret"]


async def test_wave_plays_and_sends_feedback(client):
    wave = YandexWave(client)
    await wave.init("user", "onyourwave")

    first = await wave.track()
    second = await wave.track()
    third = await wave.track()   # пачка закончилась — берём новую с фидбеком

    assert ("session", ["user:onyourwave"]) in client.calls
    assert [t.music.name for t in (first, second, third)] == ["Track 10", "Track 11", "Track 20"]
    assert first.playing_type is PlayingType.WAVE
    assert client.feedback[0] == "radioStarted"
    assert "trackFinished" in client.feedback
    # Яндексу отправляются два последних трека как контекст очереди
    assert wave.queue == ["11:5", "20:5"]


async def test_wave_skip_requests_new_batch(client):
    wave = YandexWave(client)
    await wave.init("track", "123")
    await wave.track()

    skipped = await wave.skip()

    assert "skip" in client.feedback
    assert skipped.music.name == "Track 20"
