import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class GreetingScenario(BaseModel):
    user_id: int
    guild_id: int
    sound_url: str
    disabled: bool = False
    cooldown: Optional[int] = None


class GreetingRepository:
    def __init__(self, json_path: str, default_sound_url: str = "sounds/audio.mp3"):
        print(json_path)
        self.json_path = Path(json_path)
        self.default_sound_url = default_sound_url

    def _make_key(self, guild_id: int, user_id: int) -> str:
        return f"{guild_id}:{user_id}"
    def _get_default_greeting(self,user_id:int,guild_id:int) -> GreetingScenario:
        return GreetingScenario(
            user_id=user_id,
            guild_id=guild_id,
            sound_url=self.default_sound_url
        )
    def get_greeting(self, guild_id: int, user_id: int) -> GreetingScenario:
        """Получает сценарий приветствия для пользователя в конкретной гильдии."""
        key = self._make_key(guild_id, user_id)
        data = self._load_data()
        greeting_scenario = data.get(key, self._get_default_greeting(user_id, guild_id).model_dump())
        return GreetingScenario.model_validate(greeting_scenario)

    def remove_greeting(self, guild_id: int, user_id: int) -> GreetingScenario:
        """Удаляет приветствие"""
        data = self._load_data()
        key = self._make_key(guild_id, user_id)
        ret_data = GreetingScenario.model_validate(data.pop(key))
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return ret_data

    def set_greeting(self, scenario: GreetingScenario) -> GreetingScenario:
        """Сохраняет или обновляет звук для пользователя."""
        data = self._load_data()
        key = self._make_key(scenario.guild_id, scenario.user_id)
        data[key] = scenario.model_dump(mode="json")

        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return scenario

    def _load_data(self) -> dict[str, str]:
        if not self.json_path.exists():
            return {}
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}