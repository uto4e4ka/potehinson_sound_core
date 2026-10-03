# integrations/music/track_message_service.py
from typing import Dict
from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.net_models.discord_models import NatsMessage, DiscordMessageResponse

from integrations.music.music_components import get_music_container
from integrations.music.music_embeds import get_music_embed
from integrations.music.music_models import MusicAttributes
from integrations.music.player.music_player import MusicPlayer
from integrations.music.player.providers.queue_stream_provider import QueueStreamProvider


class TrackMessageService:
    def __init__(self, discord_provider: DiscordProvider,player:MusicPlayer):
        self.discord_provider = discord_provider
        self._active_track_messages: Dict[int, DiscordMessageResponse] = {}
        self.player = player

    def id_shuffled(self,guild_id:int) -> bool:
        provider = self.player.providers.get(guild_id)
        if not provider:
            return False
        return getattr(provider, "is_shuffled", False)

    async def on_music_change(
        self, guild_id: int, text_channel_id: int, item: MusicAttributes
    ) -> None:
        """Обработка смены трека: удаляет старое сообщение и отправляет новое."""
        await self.on_music_end(guild_id)

        try:
            embed = await get_music_container(item,shuffle=self.id_shuffled(guild_id))
            raw_response = await self.discord_provider.send_message(
                NatsMessage(
                    text="",
                    containers=[embed],
                    service="",
                    channel_id=text_channel_id,
                )
            )
            self._active_track_messages[guild_id] = (
                DiscordMessageResponse.model_validate(raw_response)
            )
        except Exception as e:
            print(f"[TrackMessageService] Ошибка отправки карточки: {e}")

    async def on_music_end(self, guild_id: int, *args) -> None:
        """Удаляет активное сообщение с карточкой трека."""
        msg_response = self._active_track_messages.pop(guild_id, None)
        if not msg_response:
            return

        try:
            await self.discord_provider.remove_message(
                channel_id=msg_response.channel_id,
                message_id=msg_response.message_id,
            )
        except Exception as e:
            print(f"[TrackMessageService] Ошибка удаления сообщения: {e}")