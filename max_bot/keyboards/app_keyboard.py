from maxapi.types import OpenAppButton, ButtonsPayload
from ..settings.settings import settings


def get_app_keyboard(bot_id):

    return ButtonsPayload(
        buttons=[
            [
                OpenAppButton(
                    text="Открыть MAX Study",
                    web_app="https://yandex.ru/search/?text=Max+%D0%B4%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D1%80%D1%82%D0%B0%D1%86%D0%B8%D1%8F&lr=213&clid=2411726",
                    contact_id=None
                )
            ]
        ]
    )