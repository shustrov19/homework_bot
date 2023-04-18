class NoneEnvVarsError(Exception):
    """Недоступность переменной окружения."""

    pass


class StatusCodeIsNot200Error(Exception):
    """Ошибка ответа от API."""

    pass


class InitBotError(Exception):
    """Ошибка инициализации бота."""

    pass
