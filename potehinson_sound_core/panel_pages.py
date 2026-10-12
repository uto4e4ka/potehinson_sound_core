"""Страницы sound core в веб-панели: музыка и приветствия."""
from potehinsonnet import Plugin
from potehinsonnet.net_models import panel_models as panel
from potehinsonnet.net_models.panel_ui import (
    Button,
    Form,
    Media,
    MemberPicker,
    PanelContext,
    PanelPage,
    Table,
    TableRow,
    Text,
    TextField,
)

from potehinson_sound_core.core import Core
from potehinson_sound_core.exceptions import PlayingException
from potehinson_sound_core.greetings.repository import GreetingRepository, GreetingScenario
from potehinson_sound_core.music.player.player import MusicPlayer

# Сколько следующих треков показывать
QUEUE_PREVIEW = 20


def _duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


def register_panel_pages(
    plugin: Plugin, core: Core, player: MusicPlayer, greetings: GreetingRepository,
) -> None:

    # ------------------------------------------------------------------
    # Музыка
    # ------------------------------------------------------------------

    @plugin.panel_page("music", title="Музыка", icon="🎵")
    async def music_page(ctx: PanelContext) -> PanelPage:
        state = player.get_state(ctx.guild_id)
        if state is None:
            return PanelPage(refresh_seconds=10, blocks=[
                Text("Сейчас ничего не играет. Включить музыку можно командой /play в Discord.", style="muted"),
            ])

        track = state.track
        provider = player.providers.get(ctx.guild_id)
        blocks = [
            Media(
                title=track.music.name,
                subtitle=track.author.name if track.author else "",
                caption=_duration(track.duration) if track.duration else "",
                image_url=track.music.icon_url,
                url=track.music.url,
            ),
            Button(action="music_previous", label="⏮", disabled=not state.has_previous),
            Button(action="music_resume", label="▶️", style="primary") if state.is_paused
            else Button(action="music_pause", label="⏸"),
            Button(action="music_skip", label="⏭"),
        ]
        if hasattr(provider, "shuffle_queue"):
            blocks.append(Button(action="music_shuffle", label="🔀", active=state.is_shuffled))
        blocks.append(Button(action="music_stop", label="⏹", style="danger", confirm="Остановить музыку?"))

        queue = getattr(provider, "queue", None)
        if queue is not None:
            start = provider.current_index + 1
            upcoming = queue[start:start + QUEUE_PREVIEW]
            blocks.append(Table(
                columns=["#", "Дальше"],
                rows=[TableRow(cells=[str(i), item.music.name]) for i, item in enumerate(upcoming, start=1)],
                empty="Это последний трек в очереди",
            ))
        # Пока играет — обновляем чаще
        return PanelPage(refresh_seconds=5, blocks=blocks)

    def _require_playing(guild_id: int) -> None:
        if player.get_state(guild_id) is None:
            raise PlayingException("Сейчас ничего не играет")

    @plugin.panel_action("music_pause")
    async def music_pause(ctx: PanelContext, values: dict) -> str:
        _require_playing(ctx.guild_id)
        await player.pause_track(ctx.guild_id)
        return "⏸️ Пауза"

    @plugin.panel_action("music_resume")
    async def music_resume(ctx: PanelContext, values: dict) -> str:
        _require_playing(ctx.guild_id)
        # Продолжаем в том канале, где бот уже сидит
        connection = await core.get_connection(ctx.guild_id)
        if not connection.connected or connection.channel is None:
            raise PlayingException("Бот не в голосовом канале")
        await player.resume_track(ctx.guild_id, connection.channel.id)
        return "▶️ Продолжаем"

    @plugin.panel_action("music_skip")
    async def music_skip(ctx: PanelContext, values: dict) -> str:
        _require_playing(ctx.guild_id)
        await player.skip_track(ctx.guild_id)
        return "⏭️ Пропущено"

    @plugin.panel_action("music_previous")
    async def music_previous(ctx: PanelContext, values: dict) -> str:
        _require_playing(ctx.guild_id)
        try:
            await player.previous_track(ctx.guild_id)
        except IndexError as e:
            raise PlayingException(str(e).lstrip("❌✅ "))
        return "⏮️ Предыдущий трек"

    @plugin.panel_action("music_shuffle")
    async def music_shuffle(ctx: PanelContext, values: dict) -> str:
        _require_playing(ctx.guild_id)
        is_shuffled = await player.toggle_shuffle(ctx.guild_id)
        return "🔀 Перемешивание включено" if is_shuffled else "➡️ Перемешивание выключено"

    @plugin.panel_action("music_stop")
    async def music_stop(ctx: PanelContext, values: dict) -> str:
        await player.stop_player(ctx.guild_id)
        return "⏹️ Остановлено"

    # ------------------------------------------------------------------
    # Приветствия
    # ------------------------------------------------------------------

    async def member_names(guild_id: int, ids: list[int]) -> dict[int, str]:
        """Имена участников спрашиваем у бота; если он не отвечает — покажем ID."""
        if not ids:
            return {}
        try:
            response = await plugin.nats.request(
                panel.GUILD_MEMBERS_GET, {"guild_id": guild_id, "ids": ids}, timeout=3,
            )
        except Exception:
            # Бот выключен (таймаут или "некому ответить") — страница всё равно откроется
            return {}
        return {m.id: m.display_name or m.name for m in panel.MemberList.model_validate(response).members}

    @plugin.panel_page("greetings", title="Приветствия", icon="👋")
    async def greetings_page(ctx: PanelContext) -> PanelPage:
        items = greetings.list_greetings(ctx.guild_id)
        names = await member_names(ctx.guild_id, [g.user_id for g in items])

        rows = [
            TableRow(
                # Статус видно по кнопке "Включить"/"Выключить" и значку — отдельная колонка не нужна
                cells=[
                    names.get(g.user_id, str(g.user_id)) + (" 🔕" if g.disabled else ""),
                    g.sound_url,
                ],
                actions=[
                    Button(
                        action="greeting_toggle",
                        label="Включить" if g.disabled else "Выключить",
                        values={"user_id": str(g.user_id)},
                    ),
                    Button(
                        action="greeting_remove", label="Удалить", style="danger",
                        confirm="Удалить приветствие?", values={"user_id": str(g.user_id)},
                    ),
                ],
            )
            for g in items
        ]
        return PanelPage(blocks=[
            Text(f"Остальным играет звук по умолчанию: {greetings.default_sound_url}", style="muted"),
            Table(columns=["Участник", "Звук"], rows=rows, empty="Своих приветствий пока нет"),
            Form(action="greeting_save", submit="Сохранить приветствие", fields=[
                MemberPicker(name="user_id", label="Участник"),
                TextField(name="sound_url", label="Звук", placeholder="sounds/hello.mp3 или ссылка", required=True),
            ]),
        ])

    @plugin.panel_action("greeting_save")
    async def greeting_save(ctx: PanelContext, values: dict) -> str:
        user_id = values.get("user_id")
        sound_url = str(values.get("sound_url") or "").strip()
        if not user_id:
            raise ValueError("Выберите участника")
        if not sound_url:
            raise ValueError("Укажите звук приветствия")
        greetings.set_greeting(GreetingScenario(user_id=int(user_id), guild_id=ctx.guild_id, sound_url=sound_url))
        return "Приветствие сохранено"

    @plugin.panel_action("greeting_toggle")
    async def greeting_toggle(ctx: PanelContext, values: dict) -> str:
        user_id = int(values["user_id"])
        current = greetings.get_greeting(ctx.guild_id, user_id)
        current.disabled = not current.disabled
        greetings.set_greeting(current)
        return "Приветствие выключено" if current.disabled else "Приветствие включено"

    @plugin.panel_action("greeting_remove")
    async def greeting_remove(ctx: PanelContext, values: dict) -> str:
        try:
            greetings.remove_greeting(guild_id=ctx.guild_id, user_id=int(values["user_id"]))
        except KeyError:
            raise ValueError("Приветствие не найдено")
        return "Приветствие удалено"
