import asyncio

from max_bot.bot import bot, dp
from max_bot.handlers import register_all_routers


async def main():

    register_all_routers(dp)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())