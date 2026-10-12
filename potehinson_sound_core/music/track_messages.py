from dataclasses import dataclass
from typing import Dict

from loguru import logger
from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.net_models.discord_models import Container, DiscordMessageEdit, NatsMessage

from potehinson_sound_core.music.components import get_music_container
from potehinson_sound_core.music.embeds import extract_dominant_color
from potehinson_sound_core.music.models import MusicAttributes
from potehinson_sound_core.music.player.player import MusicPlayer, PlayerState


@dataclass
class _TrackCard:
    channel_id: int
    message_id: int
    accent_color: int | None


class TrackMessageService:
    """Карточка "Сейчас играет": новая на каждый трек, правится при паузе и перемешивании."""

    def __init__(self, discord_provider: DiscordProvider, player: MusicPlayer):
        self.discord_provider = discord_provider
        self.player = player
        self._cards: Dict[int, _TrackCard] = {}

    async def _build_card(self, track: MusicAttributes, guild_id: int, accent_color: int | None) -> Container:
        state = self.player.get_state(guild_id)
        return await get_music_container(
            track,
            shuffle=state.is_shuffled if state else False,
            paused=state.is_paused if state else False,
            has_previous=state.has_previous if state else True,
            accent_color=accent_color,
        )

    async def on_music_change(
        self, guild_id: int, text_channel_id: int, item: MusicAttributes
    ) -> None:
        """Смена трека: удаляет старую карточку и отправляет новую."""
        await self.on_music_end(guild_id)

        try:
            # Цвет считаем один раз на трек — при обновлениях карточки обложку не скачиваем
            accent_color = await extract_dominant_color(item.music.icon_url)
            card = await self._build_card(item, guild_id, accent_color)
            response = await self.discord_provider.send_message(
                NatsMessage(
                    text="",
                    containers=[card],
                    service="",
                    channel_id=text_channel_id,
                )
            )
            self._cards[guild_id] = _TrackCard(response.channel_id, response.message_id, accent_color)
        except Exception as e:
            logger.error(f"[TrackMessageService] Ошибка отправки карточки: {e}")

    async def on_state_change(self, state: PlayerState) -> None:
        """Пауза, продолжение, перемешивание: перерисовывает текущую карточку."""
        card = self._cards.get(state.guild_id)
        if card is None:
            return

        try:
            container = await get_music_container(
                state.track,
                shuffle=state.is_shuffled,
                paused=state.is_paused,
                has_previous=state.has_previous,
                accent_color=card.accent_color,
            )
            await self.discord_provider.update_message(
                DiscordMessageEdit(
                    message_id=card.message_id,
                    message=NatsMessage(
                        text="",
                        containers=[container],
                        service="",
                        channel_id=card.channel_id,
                    ),
                )
            )
        except Exception as e:
            logger.error(f"[TrackMessageService] Ошибка обновления карточки: {e}")

    async def on_music_end(self, guild_id: int, *args) -> None:
        """Удаляет активную карточку трека."""
        card = self._cards.pop(guild_id, None)
        if card is None:
            return

        try:
            await self.discord_provider.remove_message(
                channel_id=card.channel_id,
                message_id=card.message_id,
            )
        except Exception as e:
            logger.error(f"[TrackMessageService] Ошибка удаления сообщения: {e}")
