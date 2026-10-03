from potehinsonnet.net_models.discord_models import (
    ActionRow,
    ComponentButton,
    ComponentButtonStyle,
    Container,
    Separator,
    TextDisplay, ComponentThumbnail, Section,
)

from integrations.music.music_embeds import extract_dominant_color, format_duration
from integrations.music.music_models import MusicAttributes, PlayingType


async def get_music_container(
        attr: MusicAttributes,
        *,
        shuffle:bool = False,
                              ) -> Container:
    return Container(
        accent_color=await extract_dominant_color(
            attr.music.icon_url
        ),
        components=[
            Section(
                content=(
                    f"{attr.playing_type.value if (attr and attr.playing_type) else PlayingType.TRACK.value}\n"
                    f"### [{attr.music.name or 'Unknown'}]"
                    f"({attr.music.url or ''})\n"
                    f"{attr.author.name}\n"


                ),
                accessory=ComponentThumbnail(
                    url=attr.music.icon_url,
                    description=attr.music.name or "Обложка",
                ),
            ),
            TextDisplay(
                content=
                "**Длительность:**\n"
                    f"{format_duration(attr.duration)}"
            ),
            TextDisplay(
                content=
                f"-# {attr.source.value} • {attr.quality.display_name}"
            ),
            Separator(),

            ActionRow(
                components=[
                    ComponentButton(
                        label="🔀"if not shuffle else "↔️",
                        custom_id="music:shuffle",
                        style=ComponentButtonStyle.SECONDARY,
                    ),
                    ComponentButton(
                        label="⏹️",
                        custom_id="music:stop",
                        style=ComponentButtonStyle.SECONDARY,
                    ),
                ]
            ),

            ActionRow(
                components=[
                    ComponentButton(
                        label="⏮",
                        custom_id="music:prev",
                        style=ComponentButtonStyle.SECONDARY,
                    ),
                    ComponentButton(
                        label="⏸",
                        custom_id="music:pause",
                        style=ComponentButtonStyle.SECONDARY,

                    ),
                    ComponentButton(
                        label="⏭",
                        custom_id="music:skip",
                        style=ComponentButtonStyle.SECONDARY,
                    ),
                    ComponentButton(
                        label="🌊",
                        custom_id="music:wave_from_track",
                        style=ComponentButtonStyle.SECONDARY,
                        context={"track_id":f"{attr.music.id if attr.music.id else attr.music.url}"},
                    ),
                ],
            ),
        ],
    )