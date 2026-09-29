from enum import Enum, IntEnum
from typing import Optional, Callable, Awaitable

from loguru import logger
from pydantic import BaseModel, Field



class MusicSource(str,Enum):
    YANDEX_MUSIC = "YandexMusic"
    VK_MUSIC = "VkMusic"
    FILE = "File"
    SOUND_CLOUD="SoundCloud"
    POTEHINSON_TTS = "PotehinsonTTS"

class PlayingType(str, Enum):
    TRACK = "Воспроизведение трека"
    WAVE = "Моя волна"
    SPEECH = "Воспроизведение речи"


FeedbackCallback = Callable[[str, float], Awaitable[None]]

class Music(BaseModel):
    name: str
    url: str
    icon_url: str = ""
    track_url: str = ""

    feedback_callback: Optional[FeedbackCallback] = Field(
        default=None,
        exclude=True,
    )

    async def send_feedback(
        self,
        event_type: str,
        played_seconds: float = 0.0,
    ):
        """Безопасный метод отправки фидбека."""

        if not self.feedback_callback:
            return

        try:
            logger.debug(
                f"Sending music feedback: "
                f"event={event_type}, "
                f"played_seconds={played_seconds}"
            )

            await self.feedback_callback(
                event_type,
                played_seconds,
            )

        except Exception as e:
            logger.warning(
                f"Ошибка при отправке фидбека "
                f"{event_type}: {e}"
            )

class MusicAuthor(BaseModel):
    name: str = "Unknown"
    icon_url: str = ""

class MusicAlbum(BaseModel):
    name: str = ""
    icon_url: str = ""

class MusicGenre(BaseModel):
    name: str


class AudioQuality(IntEnum):
    LOW = 64
    MEDIUM = 192
    HIGH = 256
    VERY_HIGH = 320

    @property
    def display_name(self) -> str:
        match self:
            case AudioQuality.LOW:
                return "LQ"
            case AudioQuality.MEDIUM:
                return "SQ"
            case AudioQuality.HIGH:
                return "HQ"
            case AudioQuality.VERY_HIGH:
                return "HQ+"

    @classmethod
    def from_bitrate(cls, bitrate: int) -> "AudioQuality":
        """Находит точное или наиболее близкое качество по битрейту (числу)."""
        if not bitrate:
            return cls.LOW

        # Находим элемент Enum с минимальной разницей по числу
        return min(cls, key=lambda quality: abs(quality.value - bitrate))

class MusicAttributes(BaseModel):
    source: MusicSource
    duration: float
    author: MusicAuthor|None = None
    album: MusicAlbum|None = None
    genre: MusicGenre|None = None
    music: Music|None = None
    quality:AudioQuality|None = None
    playing_type:PlayingType|None = None

class MusicQueueItem(BaseModel):
    music: Music