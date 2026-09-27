from .commands import router as commands_router
from .start import router as start_router
from .text import router as text_router


def register_all_routers(dp):

    # Порядок важен: специфичные команды должны быть выше,
    # чем "поймать всё" обработчик обычного текста.
    dp.include_routers(
        start_router,
        commands_router,
        text_router,
    )
