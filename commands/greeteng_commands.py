from potehinsonnet.net_models.discord_models import (
    Command,
    CommandArgument,
    ExecutedCommand,
    ExecutedCommandResponse,
)
from potehinsonnet.setup.command_registrator import command
from scenaries.greeting_repository import GreetingRepository, GreetingScenario


class GreetingCommands:
    def __init__(self, greeting_repository: GreetingRepository):
        self.greeting_repository = greeting_repository

    @staticmethod
    def _get_arg(command: ExecutedCommand, name: str) -> str | None:
        return next((arg.value for arg in command.args if arg.name == name), None)

    @command(
        Command(
            name="add",
            description="Добавить приветствие для пользователя",
            tag="add_greeting",
            group="greeting",
            permission="sound_core.add",
            args=[
                CommandArgument(name="user", required=True, type="user", description="Пользователь"),
                CommandArgument(name="url", required=True, type="string", description="Ссылка на звук"),
            ],
        )
    )
    async def handle_add(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        url = self._get_arg(command, "url") or ""
        user_id = self._get_arg(command, "user") or "0"

        self.greeting_repository.set_greeting(
            GreetingScenario(
                user_id=int(user_id),
                guild_id=command.guild.id,
                sound_url=url,
            )
        )
        return ExecutedCommandResponse(message=f"✅ Добавлено приветствие для <@{user_id}>", is_final=True)


    @command(
        Command(
            name="remove",
            description="Удалить приветствие пользователя",
            tag="remove_greeting",
            group="greeting",
            permission="sound_core.remove",
            args=[CommandArgument(name="user", required=True, type="user", description="Пользователь")],
        )
    )
    async def handle_remove(self, command: ExecutedCommand) -> ExecutedCommandResponse:
        user_id = int(self._get_arg(command, "user") or "0")
        try:
            self.greeting_repository.remove_greeting(user_id=user_id, guild_id=command.guild.id)
            return ExecutedCommandResponse(message=f"🗑️ Удалено приветствие <@{user_id}>", is_final=True)
        except KeyError:
            return ExecutedCommandResponse(message=f"❌ Приветствие не найдено", is_final=True)