import logging

from maxapi import Router
from maxapi.filters.command import CommandStart
from maxapi.types import MessageCreated
from max_bot.keyboards.app_keyboard import get_app_keyboard

router = Router()


@router.message_created(CommandStart())
async def start_handler(event: MessageCreated):

    logging.info("Получена команда /start от %s", event.message.sender.user_id)

    keyboard = get_app_keyboard(
        bot_username=event.bot.me.username,
        bot_id=event.bot.me.user_id,
    )

    await event.message.answer(
        text="Добро пожаловать в MAX Study!",
        attachments=[keyboard.pack()],
    )
