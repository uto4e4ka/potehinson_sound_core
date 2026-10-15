"""Точка входа (plugin.toml → runtime.entry). Запуск: python -m potehinsonnet.run ."""
from potehinsonnet import Plugin, PluginContext

from potehinson_sound_core.app import create_plugin as build_plugin
from potehinson_sound_core.settings import Settings
from potehinson_sound_core.tts.generator import TTSService
from potehinson_sound_core.tts.server import create_app, run_tts_server


def create_plugin(ctx: PluginContext) -> Plugin:
    settings = Settings.from_context(ctx)
    plugin = build_plugin(settings, service=ctx.manifest.service())
    plugin.context = ctx
    plugin.add_lifespan(run_tts_server(create_app(TTSService()), host=settings.tts_host, port=settings.tts_port))
    return plugin
