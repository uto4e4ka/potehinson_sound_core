from typing import Optional

from potehinson_sound_core.music.models import MusicAttributes
from potehinson_sound_core.music.player.base import BaseStreamProvider
from potehinson_sound_core.music.radio import BaseRadio


class RadioStreamProvider(BaseStreamProvider):
    def __init__(self, radio:BaseRadio) -> None:
        self.radio = radio

    async def next_track(self) -> Optional[MusicAttributes]:
        return await self.radio.track()


    async def skip_track(self) -> Optional[MusicAttributes]:
        return await self.radio.skip()
    #
    # async def prev_track(self) -> Optional[MusicAttributes]:
    #     return await self.radio.skip()