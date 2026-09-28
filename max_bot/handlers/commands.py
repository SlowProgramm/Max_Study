from maxapi import Router
from maxapi.filters.command import Command
from maxapi.types import MessageCreated
from max_bot.bot import dp
from backend.database import SessionLocal
from backend.models import User
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





@dp.message_handler(commands=["myid", "start"])
async def cmd_myid(message):
    max_id = message.from_user.id
    username = (
        getattr(message.from_user, "username", None)
        or getattr(message.from_user, "first_name", None)
        or f"user_{max_id}"
    )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.max_id == max_id).first()
        if user is None:
            user = User(max_id=max_id, username=username)
            db.add(user)
        elif user.username != username:
            user.username = username
        db.commit()
    finally:
        db.close()

    await message.answer(
        f"Ваш MAX ID: <b>{max_id}</b>\n\n"
        f"Передайте его преподавателю, чтобы он добавил вас в класс."
    )