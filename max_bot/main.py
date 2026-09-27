import asyncio
import logging

from max_bot.bot import bot, dp
from max_bot.handlers import register_all_routers


async def main():

    # Показывает в консоли, что реально происходит: какие апдейты
    # приходят и какие исключения падают внутри хендлеров.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    register_all_routers(dp)

    # Если для этого токена когда-либо включали Webhook, start_polling
    # не будет получать апдейты, пока подписка не снята.
    await bot.delete_webhook()

    logging.info("Бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
