from dataclasses import dataclass, field
from typing import Optional, Sequence

from pydantic import BaseModel
from yandex_music import SessionFeedback

from potehinson_sound_core.music.embeds import AddingType


class YandexLink(BaseModel):
    type: AddingType
    track_id: str | None = None
    user_id: str | None = None
    playlist_id: str | None = None
    album_id: str | None = None


@dataclass
class TrackFeedback:
    id: Optional[str] = None
    start_time: Optional[float] = None
    all_time: Optional[float] = None

@dataclass
class Batch:
    sequence: list[Sequence] = field(default_factory=list)
    batch_id: Optional[str] = None
    feedback: list[SessionFeedback] = field(default_factory=list)
    last_track: Optional[TrackFeedback] = None
