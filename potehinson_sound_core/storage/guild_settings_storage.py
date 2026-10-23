from pathlib import Path
import json

from potehinsonnet.storage import DataDir
from pydantic import BaseModel


class Settings(BaseModel):
    guild_id: str
    default_enabled:bool = True


class SettingsStorage:
    def __init__(self, data: DataDir) -> None:
        self.data = data.collection("guild_settings.json",Settings,key="guild_id")

    def get_settings(self) -> Settings | None:
        return self.data.get("guild_id")

    def set_settings(self, guild_id: str, default_enabled: bool) -> None:
        self.data.put(Settings(guild_id=guild_id, default_enabled=default_enabled))
    
