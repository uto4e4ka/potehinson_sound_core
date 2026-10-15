import os
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from potehinsonnet import PluginContext

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

    @classmethod
    def from_context(cls, ctx: "PluginContext") -> "Settings":
        """Запуск через хост: .env плагина как раньше, поверх — настройки из панели, данные — в папке хоста."""
        from dotenv import load_dotenv
        load_dotenv(ctx.root / ".env")
        if ctx.settings.get("yandex_token"):
            os.environ["YANDEX_TOKEN"] = ctx.settings["yandex_token"]   # клиент Яндекса читает его отсюда
        settings = replace(cls.from_env(), nats_url=ctx.nats_url)
        if not os.getenv("GREETING_JSON_PATH"):
            greeting_json = ctx.data_dir / "greeting.json"
            legacy = ctx.root / "data" / "greeting.json"   # раньше лежал в репозитории
            if legacy.exists() and not greeting_json.exists() and legacy.resolve() != greeting_json.resolve():
                shutil.copy2(legacy, greeting_json)
            settings = replace(settings, greeting_json_path=str(greeting_json))
        overrides = {
            "greeting_enabled": ctx.settings.get("greeting"),
            "greeting_sound": ctx.settings.get("greeting_sound"),
            "tts_host": ctx.settings.get("tts_host"),
            "tts_port": int(ctx.settings["tts_port"]) if ctx.settings.get("tts_port") not in (None, "") else None,
        }
        return replace(settings, **{k: v for k, v in overrides.items() if v not in (None, "")})
