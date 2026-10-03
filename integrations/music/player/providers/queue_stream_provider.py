import random
from typing import Optional

from loguru import logger
from potehinsonnet.net_models.discord_models import Embed

from integrations.music.music_embeds import get_add_embed
from integrations.music.music_fetcher import MusicFetcher
from integrations.music.music_models import MusicAttributes, MusicQueueItem
from integrations.music.player.providers.base_stream_provider import BaseStreamProvider


class QueueStreamProvider(BaseStreamProvider):

    def __init__(self, music_fetcher: MusicFetcher) -> None:
        self.queue: list[MusicQueueItem] = []
        self._original_queue: list[MusicQueueItem] = []  # Храним исходный порядок
        self.current_index: int = -1
        self.is_shuffled: bool = False
        self.music_fetcher = music_fetcher

    async def next_track(self) -> Optional[MusicAttributes]:
        """Продвигает указатель вперед и возвращает следующий трек."""
        if self.current_index + 1 >= len(self.queue):
            return None  # Конец очереди

        self.current_index += 1
        return await self._get_current()

    async def skip_track(self) -> Optional[MusicAttributes]:
        """Скип — это просто переход к следующему треку."""
        return await self.next_track()

    def has_previous(self) -> bool:
        return self.current_index > 0

    def has_next(self) -> bool:
        return self.current_index + 1 < len(self.queue)

    async def prev_track(self) -> Optional[MusicAttributes]:
        """Откатывает указатель назад и возвращает предыдущий трек."""
        if self.current_index <= 0:
            return None  #

        self.current_index -= 1
        return await self._get_current()

    async def restart_queue(self) -> Optional[MusicAttributes]:
        """Перезапускает всю очередь с самого начала (с 0-го трека)."""
        if not self.queue:
            return None

        self.current_index = 0
        return await self._get_current()

    async def jump_to(self, index: int) -> Optional[MusicAttributes]:
        """Переход к конкретному треку по его номеру в очереди."""
        if 0 <= index < len(self.queue):
            self.current_index = index
            return await self._get_current()
        return None

    async def add_music(self, url: str) -> Embed:
        """Добавляет новые треки с учетом shuffle."""
        attrs = await self.music_fetcher.get_musics(url)

        if attrs and attrs.music_list:
            new_items = attrs.music_list

            # ВСЕГДА обновляем оригинальную очередь
            self._original_queue.extend(new_items)

            if self.is_shuffled:
                # 1. Разделяем на уже сыгранные и оставшиеся
                played = self.queue[: self.current_index + 1]
                upcoming = self.queue[self.current_index + 1:]

                # 2. Добавляем новые треки в несыгранный хвост и перемешиваем ИХ
                upcoming.extend(new_items)
                random.shuffle(upcoming)

                # 3. Собираем очередь обратно
                self.queue = played + upcoming
            else:
                self.queue.extend(new_items)

            # Точный расчёт: сколько элементов находится СТРОГО ПОСЛЕ текущего индекса
            if 0 <= self.current_index < len(self.queue):
                remaining_tracks = len(self.queue) - (self.current_index + 1)
            else:
                # Если очередь еще не запущена (current_index == -1)
                remaining_tracks = len(self.queue)

            # Записываем честный остаток очереди в атрибуты сообщения
            attrs.queue_count = remaining_tracks

        return get_add_embed(attrs)

    def shuffle_queue(self) -> bool:
        """Переключает режим shuffle."""
        if not self.queue:
            return self.is_shuffled

        if not self.is_shuffled:
            # === ВКЛЮЧАЕМ SHUFFLE ===
            # Если оригинал по какой-то причине рассинхронизирован, обновляем его
            if len(self._original_queue) != len(self.queue):
                self._original_queue = list(self.queue)

            if 0 <= self.current_index < len(self.queue):
                # Извлекаем ТЕКУЩИЙ играющий трек по его индексу
                all_tracks = list(self.queue)
                current_track = all_tracks.pop(self.current_index)

                # Перемешиваем ВСЕ остальные треки
                random.shuffle(all_tracks)

                # Ставим текущий трек на первое место (индекс 0)
                self.queue = [current_track] + all_tracks
                self.current_index = 0
            else:
                random.shuffle(self.queue)
                self.current_index = 0

            self.is_shuffled = True

        else:
            # === ВЫКЛЮЧАЕМ SHUFFLE ===
            current_track = (
                self.queue[self.current_index]
                if 0 <= self.current_index < len(self.queue)
                else None
            )

            # Восстанавливаем оригинальную очередь
            self.queue = list(self._original_queue)
            self.is_shuffled = False

            # Находим точный индекс текущего трека в оригинальной очереди
            if current_track and current_track in self.queue:
                self.current_index = self.queue.index(current_track)

        return self.is_shuffled

    async def _get_current(self) -> Optional[MusicAttributes]:
        """Безопасное получение трека по текущему `current_index`."""
        if 0 <= self.current_index < len(self.queue):
            item = self.queue[self.current_index]
            return await self._fetch_attributes(item)
        return None

    async def _fetch_attributes(self, item: MusicQueueItem) -> Optional[MusicAttributes]:
        """Загружает детали трека по его URL с обработкой ошибок."""
        try:
            return await self.music_fetcher.get_music_by_url(item.music.url)
        except Exception as e:
            logger.error(f"[QueueProvider] Ошибка загрузки трека {item.music.url}: {e}")
            # Если трек зафейлился, переходим к следующему
            return await self.next_track()