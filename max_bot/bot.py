from maxapi import Bot, Dispatcher
from max_bot.settings.settings import settings


bot = Bot(settings.max_api_key)

dp = Dispatcher()