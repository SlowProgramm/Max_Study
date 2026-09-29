from maxapi import Router
from maxapi.filters.command import Command
from maxapi.types import MessageCreated
from max_bot.bot import dp
from backend.database import SessionLocal
from backend.models import User

router = Router()

# max_id пользователей, от которых ждём ФИО после /id
pending_fio: set[int] = set()


@router.message_created(Command("help"))
async def help_handler(event: MessageCreated):
    await event.message.answer(
        "Доступные команды:\n\n"
        "/start — открыть мини-приложение MAX Study\n"
        "/help — этот список команд\n"
        "/id — показать ваш ID и указать ФИО (нужно преподавателю, чтобы добавить вас в класс)"
    )


@router.message_created(Command("id"))
async def id_handler(event: MessageCreated):
    from_user = await event.fetch_from_user()
    chat = await event.fetch_chat()

    if from_user is None or chat is None:
        await event.message.answer("Не удалось получить данные, попробуйте ещё раз.")
        return

    max_id = from_user.user_id

    # username может быть None — собираем имя из first_name + last_name
    parts = [from_user.first_name, from_user.last_name]
    name = " ".join(p for p in parts if p) or (from_user.username or f"user_{max_id}")

    # upsert в БД, чтобы преподаватель нашёл ученика по max_id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.max_id == max_id).first()
        if user is None:
            user = User(max_id=max_id, username=name)
            db.add(user)
        elif user.username != name:
            user.username = name
        db.commit()
        has_fio = bool(getattr(user, "full_name", None))
    finally:
        db.close()

    await event.message.answer(
        f"Ваш ID: <b>{max_id}</b>\n"
        f"ID этого чата: {chat.chat_id}\n\n"
        f"Передайте свой ID преподавателю, чтобы он добавил вас в класс."
    )

    # Следующим сообщением просим Фамилию Имя
    pending_fio.add(max_id)
    if has_fio:
        await event.message.answer(
            "ФИО уже сохранено. Чтобы изменить — напишите заново в формате:\n"
            "<b>Фамилия Имя</b>\n"
            "Например: <i>Иванов Иван</i>"
        )
    else:
        await event.message.answer(
            "Пожалуйста, напишите вашу <b>Фамилию и Имя</b> следующим сообщением.\n"
            "Например: <i>Иванов Иван</i>\n\n"
            "Это нужно, чтобы преподаватель видел вас в журнале по ФИО."
        )
