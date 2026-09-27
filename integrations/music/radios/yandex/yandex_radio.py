import time
from typing import Optional, List

from yandex_music import ClientAsync, RotorSession, Track, SessionFeedback, SessionEvent

from integrations.music.radios.radio import BaseRadio
from integrations.music.radios.yandex.models import Batch, TrackFeedback
from integrations.music.radios.yandex.utils import get_formatted_track_id, get_time



def get_played_time(start_time: float) -> float:
    """Возвращает количество проигранных секунд текущего трека."""
    if not start_time:
        return 0.0
    return round(time.time() - start_time, 2)


class YandexWave(BaseRadio):
    def __init__(self, client: ClientAsync, queue: Optional[list[str]] = None) -> None:
        self.client: ClientAsync = client
        self._session: Optional[RotorSession] = None
        self.batch: Optional[Batch] = None
        self.queue: list[str] = queue if queue is not None else []

    async def init(self, type: str, tag: str) -> None:
        self._session = await self.create_or_clone_session(type, tag)
        await self.client.rotor_session_feedback_radio_started(self._session.radio_session_id or "",from_="radio-mobile-wave_screen-clean-default")

    async def create_or_clone_session(self, type: str, tag: str, session: str = "") -> Optional[RotorSession]:
        if not session:
            return await self.client.rotor_session_new(seeds=[f"{type}:{tag}"], include_tracks_in_response=False)
        return await self.client.rotor_session_clone(radio_session_id=session)

    async def new_batch(self, feedback: Optional[List[SessionFeedback]] = None) -> None:
        print(f"new batch: {feedback}")
        session_id = self._session.radio_session_id if self._session else ""
        tracks = await self.client.rotor_session_tracks(
            session_id or "",
            queue=self.queue,
            feedbacks=feedback
        )
        self.batch = Batch(
            sequence=tracks.sequence,
            batch_id=tracks.batch_id,
            feedback=[],
            last_track=None
        )

    async def last_track(self) -> Optional[Track]:
        current_feedback = self.batch.feedback if self.batch else None
        is_first = False
        if not self.batch or not self.batch.sequence:
            await self.new_batch(feedback=current_feedback)
            is_first = True

        try:

            track = self.batch.sequence.pop(0).track  # Берем с начала пачки (pop(0))
            if is_first:
                await self.client.rotor_session_feedback_track_started(self._session.radio_session_id,
                                                                       track_id=get_formatted_track_id(track),
                                                                        batch_id=self.batch.batch_id,
                                                                       from_="radio-mobile-wave_screen-clean-default",
                                                                       )
            return track
        except (IndexError, AttributeError):
            await self.new_batch(feedback=current_feedback)
            return self.batch.sequence.pop(0).track

    async def track(self) -> Optional[Track]:
        # 1. Если трек уже играл — отправляем фидбек о полном прослушивании
        if self.batch and self.batch.last_track and self.batch.last_track.id:
            last_track = self.batch.last_track
            self.batch.feedback.append(
                SessionFeedback(
                    event=SessionEvent(
                        type="trackFinished",
                        timestamp=get_time(),
                        track_id=last_track.id,
                        total_played_seconds=get_played_time(last_track.start_time or 0.0),
                    ),
                    batch_id=self.batch.batch_id,
                    from_="radio-mobile-wave_screen-clean-default"
                )
            )

        # 2. Достаем следующий трек
        track_ = await self.last_track()
        if not track_:
            return None

        # 3. Безопасно обновляем информацию о текущем треке
        duration = (track_.duration_ms / 1000) if track_.duration_ms else 0.0
        self.batch.last_track = TrackFeedback(
            id=get_formatted_track_id(track_),
            start_time=time.time(),
            all_time=duration
        )
        self.__add_queue(track_)
        return track_

    async def skip(self) -> Optional[Track]:
        # 1. Формируем фидбек о скипе текущего трека
        if self.batch and self.batch.last_track and self.batch.last_track.id:
            feedback = SessionFeedback(
                batch_id=self.batch.batch_id,  # Передаем batch_id, а не track_id
                event=SessionEvent(
                    type="skip",
                    timestamp=get_time(),
                    track_id=self.batch.last_track.id,
                    total_played_seconds=get_played_time(self.batch.last_track.start_time or 0.0)
                ),
                from_="radio-mobile-wave_screen-clean-default"
            )
            self.batch.feedback.append(feedback)

        # 2. При скипе запрашиваем новый батч треков с отправкой фидбека
        await self.new_batch(self.batch.feedback if self.batch else None)

        # 3. Берем первый трек из нового батча
        track_ = await self.last_track()
        if not track_:
            return None

        # 4. Обновляем текущий трек
        duration = (track_.duration_ms / 1000) if track_.duration_ms else 0.0
        self.batch.last_track = TrackFeedback(
            id=get_formatted_track_id(track_),
            start_time=time.time(),
            all_time=duration
        )
        self.__add_queue(track_)
        return track_

    def __add_queue(self, track: Optional[Track]) -> None:
        if track:
            self.queue.append(get_formatted_track_id(track))
            self.queue = self.queue[-2:]