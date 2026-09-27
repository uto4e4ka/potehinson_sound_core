import asyncio
import random
from datetime import datetime, timezone
from yandex_music import ClientAsync, SessionFeedback, SessionEvent

from integrations.music.radios.yandex.yandex_radio import YandexWave

TOKEN = "y0__wgBEOy528ACGN74BiDwr8j-GI_duTInxfTvnpB5XJ7c5I-Io0Gc"



async def async_main():
    client: ClientAsync = ClientAsync(token=TOKEN)
    #
    # queue = ["154108903:43261475", "117886597:27604223"]
    #
    # session = await client.rotor_session_new(
    #     seeds=["user:onyourwave"],
    #     queue=queue,
    #     incognito=False  # incognito=False дает более глубокую персональную подборку
    # )
    #
    # curr_track = session.sequence[0].track
    # curr_batch = session.batch_id
    # session_id = session.radio_session_id or ""
    #
    # def get_formatted_track_id(track) -> str:
    #     track_id = getattr(track, 'real_id', track.id)
    #     album_id = track.albums[0].id if track.albums else "0"
    #     return f"{track_id}:{album_id}"
    #
    # await client.rotor_session_feedback_radio_started(
    #     radio_session_id=session_id,
    #     from_="web-wave_landing_screen-my_wave-radio-default"
    # )
    #
    # step = 0
    # while True:
    #     step += 1
    #     formatted_curr_track_id = get_formatted_track_id(curr_track)
    #
    #     # 1. Обязательно сигнализируем о начале воспроизведения трека
    #     await client.rotor_session_feedback_track_started(
    #         radio_session_id=session_id,
    #         from_="web-wave_landing_screen-my_wave-radio-default",
    #         track_id=formatted_curr_track_id
    #     )
    #
    #     # Каждые 3 трека имитируем полное прослушивание, иначе — скип
    #     is_full_listen = (step % 3 == 0)
    #
    #     if is_full_listen:
    #         play_time = (curr_track.duration_ms // 1000) if curr_track.duration_ms else 120
    #         event_type = "trackFinished"
    #         print(f"[Имитация прослушивания {play_time} сек...]")
    #         await asyncio.sleep(2)  # Для тестов держим паузу короткой
    #     else:
    #         play_time = random.randint(7, 15)
    #         event_type = "skip"
    #         await asyncio.sleep(3)
    #
    #     timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    #
    #     # 2. Отправляем полноценный фидбек
    #     new_track_ = await client.rotor_session_tracks(
    #         radio_session_id=session_id,
    #         feedbacks=[
    #             SessionFeedback(
    #                 event=SessionEvent(
    #                     type=event_type,
    #                     total_played_seconds=float(play_time),
    #                     track_id=formatted_curr_track_id,
    #                     timestamp=timestamp_utc,
    #                 ),
    #                 batch_id=curr_batch,
    #             )
    #         ]
    #     )
    #
    #     curr_track = new_track_.sequence[0].track
    #     curr_batch = new_track_.batch_id
    #
    #     queue.append(formatted_curr_track_id)
    #     queue = queue[-2:]
    #
    #     artist_name = curr_track.artists[0].name if curr_track.artists else "Unknown"
    #     print(f"Playing: {artist_name} - {curr_track.title} | Event: {event_type}")
    #     print(f"Updated queue: {queue}\n")
    wave = YandexWave(client=client)
    await wave.init(type="user",tag="onyourwave",session="S13y-tYtfP5OiKpxJZp-KdjV")
    print(await wave.track())
    await asyncio.sleep(5)
    print(await wave.track())
    await asyncio.sleep(5)
    print(await wave.track())
    await asyncio.sleep(5)
    print(await wave.track())
    await asyncio.sleep(5)
    print(await wave.skip())
    await asyncio.sleep(5)


asyncio.run(async_main())