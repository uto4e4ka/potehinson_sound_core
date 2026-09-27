from dataclasses import dataclass, field
from typing import Sequence, Optional

from yandex_music import SessionFeedback


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
