from maxapi.types import ButtonsPayload, OpenAppButton


def get_app_keyboard(bot_username: str, bot_id: int) -> ButtonsPayload:
    """
    Кнопка открытия мини-приложения.

    Важно: `web_app` — это username самого бота, а не произвольная ссылка.
    Мини-приложение открывается то, что настроено в MasterBot для этого
    бота (Мини-приложения -> ссылка на сайт), передать другую ссылку
    через код нельзя.
    """

    return ButtonsPayload(
        buttons=[
            [
                OpenAppButton(
                    text="Открыть Синапс",
                    web_app=bot_username, #ЭТО ПЕРЕХОД НА МИНИ ПРИЛОЖЕНИЕ
                    contact_id=bot_id,
                )
            ]
        ]
    )
