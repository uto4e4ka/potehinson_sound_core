from integrations.music.music_embeds import MusicAddMessage, AddingType
from integrations.music.music_models import MusicAttributes, MusicSource, MusicQueueItem, Music, MusicAuthor, \
    AudioQuality, PlayingType
from integrations.music.resolvers.resolver import BaseResolver


class TtsResolver(BaseResolver):

    async def find_musics(self, url: str) -> MusicAddMessage:
        return MusicAddMessage(
            add_type=AddingType.SAY,
            source=MusicSource.POTEHINSON_TTS,
            name="Phrase TTS",
            music_list=[
                MusicQueueItem(
                    music = Music(
                        name="Фраза",
                        url = url
                    )
                )
            ]
        )

    async def get_track_by_url(self, url) -> MusicAttributes:
        return MusicAttributes(
            source=MusicSource.POTEHINSON_TTS,
            duration=0,
            playing_type=PlayingType.SPEECH,
            music=Music(
                name="Phrase TTS",
                track_url=url,
                url=""
            ),
            author= MusicAuthor(
                name="Potehinson",
            ),
            quality=AudioQuality.LOW,
        )

    def can_resolve(self, url) -> bool:
        return "http://localhost:8000/integrations/tts" in url

