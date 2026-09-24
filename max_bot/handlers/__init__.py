from .start import router as start_router
from .text import router as text_router


def register_all_routers(dp):

    dp.include_routers(
        start_router,
        text_router
    )