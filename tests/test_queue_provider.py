import pytest

from potehinson_sound_core.music.player.queue import QueueStreamProvider
from tests.conftest import FakeFetcher


@pytest.fixture
def queue(fetcher) -> QueueStreamProvider:
    return QueueStreamProvider(fetcher)


async def names(provider, method="next_track", times=1):
    result = []
    for _ in range(times):
        item = await getattr(provider, method)()
        result.append(item.music.name if item else None)
    return result


async def test_plays_in_order_then_ends(queue):
    await queue.add_music("list:a,b,c")

    assert await names(queue, times=4) == ["a", "b", "c", None]


async def test_previous_and_navigation(queue):
    await queue.add_music("list:a,b,c")
    await names(queue, times=2)   # сейчас играет b

    assert queue.has_previous() and queue.has_next()
    assert await names(queue, "prev_track") == ["a"]
    assert not queue.has_previous()
    assert await names(queue, "prev_track") == [None]
    assert (await queue.jump_to(2)).music.name == "c"
    assert await queue.jump_to(10) is None
    assert (await queue.restart_queue()).music.name == "a"
    assert await names(queue, "skip_track") == ["b"]


async def test_restart_empty_queue(queue):
    assert await queue.restart_queue() is None


async def test_add_embed_counts_remaining_tracks(queue):
    first = await queue.add_music("list:a,b")
    await queue.next_track()
    second = await queue.add_music("list:c")

    def field(embed, name):
        return next(f.value for f in embed.fields if f.name == name)

    assert field(first, "Всего в очереди") == "2"
    assert field(second, "Добавлено треков") == "1"
    assert field(second, "Всего в очереди") == "2"   # b и c


async def test_shuffle_keeps_current_track_first(queue, monkeypatch):
    monkeypatch.setattr("random.shuffle", lambda items: items.reverse())
    await queue.add_music("list:a,b,c,d")
    await names(queue, times=2)   # играет b

    assert queue.shuffle_queue() is True

    assert queue.queue[0].music.name == "b"
    assert await names(queue, times=3) == ["d", "c", "a"]


async def test_unshuffle_restores_order_and_position(queue, monkeypatch):
    monkeypatch.setattr("random.shuffle", lambda items: items.reverse())
    await queue.add_music("list:a,b,c,d")
    await names(queue)   # a
    queue.shuffle_queue()
    await names(queue)   # d (после перемешивания)

    assert queue.shuffle_queue() is False

    assert [i.music.name for i in queue.queue] == ["a", "b", "c", "d"]
    assert await names(queue) == [None]   # d был последним в исходном порядке


async def test_tracks_added_while_shuffled_go_to_upcoming(queue, monkeypatch):
    monkeypatch.setattr("random.shuffle", lambda items: None)
    await queue.add_music("list:a,b")
    await names(queue)
    queue.shuffle_queue()

    await queue.add_music("list:c")

    assert [i.music.name for i in queue.queue] == ["a", "b", "c"]
    assert [i.music.name for i in queue._original_queue] == ["a", "b", "c"]


async def test_shuffle_empty_queue(queue):
    assert queue.shuffle_queue() is False


async def test_broken_track_is_skipped():
    provider = QueueStreamProvider(FakeFetcher(broken={"b"}))
    await provider.add_music("list:a,b,c")

    assert await names(provider, times=3) == ["a", "c", None]
