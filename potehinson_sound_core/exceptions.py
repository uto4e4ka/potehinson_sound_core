class PlayingException(Exception):
    pass


class BotBusyException(Exception):
    """Бот уже играет в другом голосовом канале."""
