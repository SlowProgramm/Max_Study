from maxapi import F, Router
from maxapi.types import MessageCreated

from backend.database import SessionLocal
from backend.models import User
from max_bot.handlers.commands import pending_fio
from max_bot.keyboards.menus import WELCOME_TEXT, build_role_keyboard

router = Router()


@router.message_created(F.message.body.text)
async def text_handler(event: MessageCreated):
    from_user = await event.fetch_from_user()
    if from_user is None:
        return

    max_id = from_user.user_id
    text = (event.message.body.text or "").strip()

    if not text or text.startswith("/"):
        return

    # Ждём ФИО только после /id или «Запросить ID»
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
                "Пожалуйста, укажите и Фамилию, и Имя.\n"
                "Пример: Петров Пётр"
            )
            return

        user.full_name = " ".join(words[:4])
        db.commit()
        pending_fio.discard(max_id)

        await event.message.answer(
            f"ФИО сохранено: {user.full_name}\n\n"
            f"Ваш ID: {max_id} — передайте его преподавателю."
        )
        # Снова основное меню
        await event.message.answer(
            text=WELCOME_TEXT,
            attachments=[build_role_keyboard().as_markup()],
        )
    finally:
        db.close()
