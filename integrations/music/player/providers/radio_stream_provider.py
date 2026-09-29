from idlelib.window import add_windows_to_menu
from typing import Optional

from integrations.music.music_models import MusicAttributes
from integrations.music.player.providers.base_stream_provider import BaseStreamProvider
from integrations.music.radios.radio import BaseRadio


class RadioStreamProvider(BaseStreamProvider):
    def __init__(self, radio:BaseRadio) -> None:
        self.radio = radio

    async def next_track(self) -> Optional[MusicAttributes]:
        return await self.radio.track()


    async def skip_track(self) -> Optional[MusicAttributes]:
        return await self.radio.skip()