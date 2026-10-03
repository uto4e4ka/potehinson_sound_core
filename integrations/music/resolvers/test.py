import asyncio
import re

from yandex_music import ClientAsync


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


async def search(query: str):
    client = await ClientAsync(
        ""
    ).init()

    normalized_query = normalize(query)

    # 1. Сначала специально ищем артистов
    artist_result = await client.search(
        query,
        type_="artist",
    )

    artists = (
        artist_result.artists.results
        if artist_result.artists
        else []
    )

    # Ищем наиболее подходящего артиста
    for artist in artists:
        name = normalize(artist.name)

        if name == normalized_query:
            return {
                "type": "artist",
                "result": artist,
            }

    # Частичное совпадение
    for artist in artists:
        name = normalize(artist.name)

        if normalized_query in name or name in normalized_query:
            return {
                "type": "artist",
                "result": artist,
            }

    # 2. Если артист не найден — ищем треки
    track_result = await client.search(
        query,
        type_="track",
    )

    tracks = (
        track_result.tracks.results
        if track_result.tracks
        else []
    )

    if tracks:
        return {
            "type": "track",
            "result": tracks[0],
        }

    return None


async def get():
    result = await search("Мейби Бэйби")

    if result:
        print(result["type"])
        print(result["result"])


asyncio.run(get())