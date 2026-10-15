"""python -m potehinson_sound_core — то же, что python -m potehinsonnet.run <корень плагина>."""
import sys

from potehinsonnet.run import main

from potehinson_sound_core.settings import PROJECT_ROOT


def run() -> None:
    sys.exit(main([str(PROJECT_ROOT)]))


if __name__ == "__main__":
    run()
