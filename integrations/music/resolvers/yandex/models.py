from pydantic import BaseModel

from integrations.music.music_embeds import AddingType


class YandexLink(BaseModel):
    type: AddingType
    track_id: str | None = None
    user_id: str | None = None
    playlist_id: str | None = None
    album_id: str | None = None