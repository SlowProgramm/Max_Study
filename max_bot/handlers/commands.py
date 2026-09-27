from maxapi import Router
from maxapi.filters.command import Command
from maxapi.types import MessageCreated

router = Router()


@router.message_created(Command("help"))
async def help_handler(event: MessageCreated):
    await event.message.answer(
        "Доступные команды:\n\n"
        "/start — открыть мини-приложение MAX Study\n"
        "/help — этот список команд\n"
        "/id — показать ваш ID и ID чата"
    )


@router.message_created(Command("id"))
async def id_handler(event: MessageCreated):
    from_user = await event.fetch_from_user()
    chat = await event.fetch_chat()

    if from_user is None or chat is None:
        await event.message.answer("Не удалось получить данные, попробуйте ещё раз.")
        return

    await event.message.answer(
        f"Ваш ID: {from_user.user_id}\n"
        f"ID этого чата: {chat.chat_id}"
    )
