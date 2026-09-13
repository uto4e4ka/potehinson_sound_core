from enum import Enum

from pydantic import BaseModel


class MusicSource(str,Enum):
    YANDEX_MUSIC = "YandexMusic"
    VK_MUSIC = "VkMusic"
    FILE = "File"
    SOUND_CLOUD="SoundCloud"

class Music(BaseModel):
    name:str
    url:str
    icon_url:str =""
    track_url:str=""

class MusicAuthor(BaseModel):
    name: str = "Unknown"
    icon_url: str = ""

class MusicAlbum(BaseModel):
    name: str = ""
    icon_url: str = ""

class MusicGenre(BaseModel):
    name: str

class MusicAttributes(BaseModel):
    source: MusicSource
    duration: float
    author: MusicAuthor|None = None
    album: MusicAlbum|None = None
    genre: MusicGenre|None = None
    music: Music|None = None

class MusicQueueItem(BaseModel):
    music: Music