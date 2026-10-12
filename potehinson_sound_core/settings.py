import os
from dataclasses import dataclass
from pathlib import Path

# Корень репозитория — чтобы пути не зависели от каталога, из которого запущен плагин
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    nats_url: str = "nats://localhost:4222"
    greeting_enabled: bool = False
    # Путь к звуку открывает бот, относительно своего рабочего каталога
    greeting_sound: str = "sounds/audio.mp3"
    greeting_json_path: str = str(PROJECT_ROOT / "data" / "greeting.json")
    tts_host: str = "0.0.0.0"
    tts_port: int = 8000

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            nats_url=os.getenv("NATS_URL", defaults.nats_url),
            greeting_enabled=_env_bool("GREETING"),
            greeting_sound=os.getenv("GREETING_SOUND") or defaults.greeting_sound,
            greeting_json_path=os.getenv("GREETING_JSON_PATH", defaults.greeting_json_path),
            tts_host=os.getenv("TTS_HOST", defaults.tts_host),
            tts_port=int(os.getenv("TTS_PORT", defaults.tts_port)),
        )
