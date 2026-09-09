import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class GreetingScenario(BaseModel):
    user_id: int
    guild_id: int
    sound_url: str


class GreetingRepository:
    def __init__(self, json_path: str, default_sound_url: str = "media/sounds/default.mp3"):
        print(json_path)
        self.json_path = Path(json_path)
        self.default_sound_url = default_sound_url

    def _make_key(self, guild_id: int, user_id: int) -> str:
        return f"{guild_id}:{user_id}"

    def get_greeting(self, guild_id: int, user_id: int) -> GreetingScenario:
        """Получает сценарий приветствия для пользователя в конкретной гильдии."""
        key = self._make_key(guild_id, user_id)
        data = self._load_data()

        sound_url = data.get(key, self.default_sound_url)
        return GreetingScenario(user_id=user_id, guild_id=guild_id, sound_url=sound_url)

    def set_greeting(self, scenario: GreetingScenario) -> None:
        """Сохраняет или обновляет звук для пользователя."""
        data = self._load_data()
        key = self._make_key(scenario.guild_id, scenario.user_id)
        data[key] = scenario.sound_url

        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_data(self) -> dict[str, str]:
        if not self.json_path.exists():
            return {}
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}