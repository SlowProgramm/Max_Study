import logging

from maxapi import Router
from maxapi.filters.command import CommandStart
from maxapi.types import MessageCreated

from max_bot.keyboards.menus import WELCOME_TEXT, build_role_keyboard

router = Router()


@router.message_created(CommandStart())
async def start_handler(event: MessageCreated):

    logging.info("Получена команда /start от %s", event.message.sender.user_id)

    await event.message.answer(
        text=WELCOME_TEXT,
        attachments=[build_role_keyboard().as_markup()],
    )
