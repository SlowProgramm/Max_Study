from maxapi import Router
from maxapi.filters.command import Command
from maxapi.types import MessageCreated

from backend.database import SessionLocal
from backend.models import User

router = Router()

# max_id пользователей, от которых ждём ФИО после /id
pending_fio: set[int] = set()


def upsert_user(max_id: int, name: str) -> bool:
    """Создаёт/обновляет пользователя. Возвращает has_fio."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.max_id == max_id).first()
        if user is None:
            user = User(max_id=max_id, username=name)
            db.add(user)
        elif user.username != name:
            user.username = name
        db.commit()
        db.refresh(user)
        return bool(getattr(user, "full_name", None))
    finally:
        db.close()


@router.message_created(Command("help"))
async def help_handler(event: MessageCreated):
    await event.message.answer(
        "Команды:\n\n"
        "/start — меню MAX Study\n"
        "/help — этот список\n"
        "/id — показать ваш ID и указать ФИО"
    )


@router.message_created(Command("id"))
async def id_handler(event: MessageCreated):
    from_user = await event.fetch_from_user()
    chat = await event.fetch_chat()

    if from_user is None:
        await event.message.answer("Не удалось получить данные, попробуйте ещё раз.")
        return

    max_id = from_user.user_id
    parts = [from_user.first_name, from_user.last_name]
    name = " ".join(p for p in parts if p) or (from_user.username or f"user_{max_id}")

    has_fio = upsert_user(max_id, name)

    chat_line = f"\nID чата: {chat.chat_id}" if chat else ""
    await event.message.answer(
        f"Ваш ID: {max_id}{chat_line}\n\n"
        "Передайте свой ID преподавателю, чтобы он добавил вас в класс."
    )

    pending_fio.add(max_id)
    if has_fio:
        await event.message.answer(
            "ФИО уже сохранено. Чтобы изменить — напишите заново в формате:\n"
            "Фамилия Имя\n"
            "Например: Иванов Иван"
        )
    else:
        await event.message.answer(
            "Пожалуйста, напишите вашу Фамилию и Имя следующим сообщением.\n"
            "Например: Иванов Иван\n\n"
            "Это нужно, чтобы преподаватель видел вас в журнале по ФИО."
        )
