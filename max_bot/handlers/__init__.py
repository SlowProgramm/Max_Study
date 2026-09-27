from .commands import router as commands_router
from .menu_callbacks import router as menu_callbacks_router
from .start import router as start_router
from .text import router as text_router


def register_all_routers(dp):

    # Порядок важен: специфичные команды/колбэки должны быть выше,
    # чем "поймать всё" обработчик обычного текста.
    dp.include_routers(
        start_router,
        menu_callbacks_router,
        commands_router,
        text_router,
    )
