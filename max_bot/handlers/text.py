from maxapi import F, Router
from maxapi.types import MessageCreated

from backend.database import SessionLocal
from backend.models import User
from max_bot.handlers.commands import pending_fio

router = Router()


@router.message_created(F.message.body.text)
async def text_handler(event: MessageCreated):
    from_user = await event.fetch_from_user()
    if from_user is None:
        return

    max_id = from_user.user_id
    text = (event.message.body.text or "").strip()

    # Команды обрабатываются другими хендлерами
    if not text or text.startswith("/"):
        return

    # Ждём ФИО только после /id
    if max_id not in pending_fio:
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.max_id == max_id).first()
        if user is None:
            parts = [from_user.first_name, from_user.last_name]
            name = " ".join(p for p in parts if p) or (from_user.username or f"user_{max_id}")
            user = User(max_id=max_id, username=name)
            db.add(user)
            db.commit()
            db.refresh(user)

        words = [w for w in text.split() if w]
        if len(words) < 2:
            await event.message.answer(
                "Пожалуйста, укажите и <b>Фамилию</b>, и <b>Имя</b>.\n"
                "Пример: <i>Петров Пётр</i>"
            )
            return

        user.full_name = " ".join(words[:4])  # Фамилия Имя [Отчество]
        db.commit()
        pending_fio.discard(max_id)
        await event.message.answer(
            f"✅ ФИО сохранено: <b>{user.full_name}</b>\n\n"
            f"Ваш ID: <b>{max_id}</b> — передайте его преподавателю."
        )
    finally:
        db.close()
