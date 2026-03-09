from helm_telegram_bot.guards import is_allowed_user


class _User:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _Update:
    def __init__(self, user_id: int) -> None:
        self.effective_user = _User(user_id)


def test_guard_callable() -> None:
    update = _Update(1)
    assert isinstance(is_allowed_user(update), bool)
