from potehinsonnet.net_models.discord_models import Container, TextDisplay, Separator, ActionRow, ComponentButton, \
    ComponentButtonStyle

from integrations.music.music_models import MusicAttributes


def get_music_container(attr:MusicAttributes)->Container:
    return Container(
                    accent_color=0x5865F2,
                    components=[
                       TextDisplay(
                           content="## Сейчас играет"
                       ),

                       TextDisplay(
                           content="**Мейби Бэйби — Мой ненаглядный**"
                       ),

                       Separator(),

                       ActionRow(
                           components=[
                               ComponentButton(
                                   label="⏮",
                                   custom_id="music:previous",
                                   style=ComponentButtonStyle.PRIMARY,
                               ),
                               ComponentButton(
                                   label="⏸",
                                   custom_id="music:pause",
                                   style=ComponentButtonStyle.PRIMARY,
                               ),
                               ComponentButton(
                                   label="⏭",
                                   custom_id="music:skip",
                                   style=ComponentButtonStyle.SECONDARY,
                               ),
                           ]
                       ),
                    ],
                    )

