import logging

from maxapi import Router
from maxapi.types.updates.message_callback import MessageCallback

from backend.database import SessionLocal
from backend.models import Class, ClassMember, Question, Test, TestAttempt, User
from max_bot.handlers.commands import pending_fio
from max_bot.keyboards.menus import (
    STUDENT_TEXT,
    TEACHER_TEXT,
    WELCOME_TEXT,
    BackPayload,
    RolePayload,
    StudentSectionPayload,
    TeacherSectionPayload,
    build_back_to_student,
    build_back_to_teacher,
    build_class_detail_keyboard,
    build_role_keyboard,
    build_student_history_keyboard,
    build_student_keyboard,
    build_teacher_keyboard,
    build_teacher_tests_keyboard,
)

router = Router()


def _bot_app_ids(event: MessageCallback) -> tuple[str, int]:
    me = event.bot.me
    return me.username, me.user_id


def _display_name(user: User | None) -> str:
    if not user:
        return "—"
    name = (getattr(user, "full_name", None) or user.username or "").strip()
    return name or "—"


@router.message_callback(RolePayload.filter())
async def on_role_selected(event: MessageCallback, payload: RolePayload):
    logging.info("Выбрана роль: %s", payload.role)
    await event.answer()
    bot_username, bot_id = _bot_app_ids(event)

    if payload.role == "teacher":
        await event.edit(
            text=TEACHER_TEXT,
            attachments=[build_teacher_keyboard(bot_username, bot_id).as_markup()],
        )
    else:
        await event.edit(
            text=STUDENT_TEXT,
            attachments=[build_student_keyboard(bot_username, bot_id).as_markup()],
        )


@router.message_callback(TeacherSectionPayload.filter())
async def on_teacher_section(event: MessageCallback, payload: TeacherSectionPayload):
    await event.answer()
    bot_username, bot_id = _bot_app_ids(event)

    from_user = event.callback.user if hasattr(event, "callback") else None
    # Получаем max_id автора callback
    max_id = None
    try:
        if event.callback and event.callback.user:
            max_id = event.callback.user.user_id
    except Exception:
        pass
    if max_id is None:
        try:
            max_id = event.message.sender.user_id
        except Exception:
            max_id = None

    if payload.section == "class":
        await _show_teacher_class(event, bot_username, bot_id, max_id)
    elif payload.section == "my_tests":
        await _show_teacher_tests(event, bot_username, bot_id, max_id)


async def _show_teacher_class(event, bot_username, bot_id, max_id):
    if not max_id:
        await event.edit(
            text="Не удалось определить пользователя. Напишите /start.",
            attachments=[build_back_to_teacher().as_markup()],
        )
        return

    db = SessionLocal()
    try:
        teacher = db.query(User).filter(User.max_id == max_id).first()
        if not teacher:
            await event.edit(
                text="Вы ещё не зарегистрированы. Откройте мини-приложение один раз или напишите /id.",
                attachments=[build_back_to_teacher().as_markup()],
            )
            return

        classes = (
            db.query(Class)
            .filter(Class.teacher_id == teacher.id)
            .order_by(Class.name)
            .all()
        )
        if not classes:
            await event.edit(
                text="У вас пока нет классов.\nДобавьте класс в мини-приложении (Мой класс).",
                attachments=[build_class_detail_keyboard(bot_username, bot_id, None).as_markup()],
            )
            return

        # Последний опубликованный тест учителя
        last_test = (
            db.query(Test)
            .filter(Test.creator_id == teacher.id, Test.is_draft.is_(False))
            .order_by(Test.id.desc())
            .first()
        )
        q_count = 0
        if last_test:
            q_count = db.query(Question).filter(Question.test_id == last_test.id).count()

        lines = ["Мой класс\n"]
        if last_test:
            lines.append(f"Последний тест: {last_test.title or 'Без названия'}\n")
        else:
            lines.append("Опубликованных тестов пока нет.\n")

        for cls in classes:
            lines.append(f"\n{cls.name}")
            members = (
                db.query(ClassMember)
                .filter(ClassMember.class_id == cls.id)
                .all()
            )
            if not members:
                lines.append("  (пусто)")
                continue
            for m in members:
                st = db.query(User).filter(User.id == m.student_id).first()
                name = _display_name(st)
                score_str = "—"
                if last_test and q_count:
                    att = (
                        db.query(TestAttempt)
                        .filter(
                            TestAttempt.test_id == last_test.id,
                            TestAttempt.student_id == m.student_id,
                            TestAttempt.score.isnot(None),
                        )
                        .order_by(TestAttempt.id.desc())
                        .first()
                    )
                    if att and att.score is not None:
                        pct = round(att.score / q_count * 100)
                        score_str = f"{att.score}/{q_count} ({pct}%)"
                lines.append(f"  {name}: {score_str}")

        text = "\n".join(lines)
        if len(text) > 3500:
            text = text[:3500] + "\n…"

        await event.edit(
            text=text,
            attachments=[
                build_class_detail_keyboard(
                    bot_username, bot_id, last_test.id if last_test else None
                ).as_markup()
            ],
        )
    finally:
        db.close()


async def _show_teacher_tests(event, bot_username, bot_id, max_id):
    if not max_id:
        await event.edit(
            text="Не удалось определить пользователя.",
            attachments=[build_back_to_teacher().as_markup()],
        )
        return

    db = SessionLocal()
    try:
        teacher = db.query(User).filter(User.max_id == max_id).first()
        if not teacher:
            await event.edit(
                text="Сначала откройте мини-приложение или напишите /id.",
                attachments=[build_back_to_teacher().as_markup()],
            )
            return

        tests = (
            db.query(Test)
            .filter(Test.creator_id == teacher.id)
            .order_by(Test.id.desc())
            .limit(3)
            .all()
        )
        items = [{"id": t.id, "title": t.title or "Без названия"} for t in tests]

        if not items:
            text = "Тестов пока нет.\nСоздайте первый через «Создать тест»."
        else:
            lines = ["Последние тесты:\n"]
            for i, t in enumerate(items, 1):
                lines.append(f"{i}. {t['title']}")
            text = "\n".join(lines)

        await event.edit(
            text=text,
            attachments=[
                build_teacher_tests_keyboard(bot_username, bot_id, items).as_markup()
            ],
        )
    finally:
        db.close()


@router.message_callback(StudentSectionPayload.filter())
async def on_student_section(event: MessageCallback, payload: StudentSectionPayload):
    await event.answer()
    bot_username, bot_id = _bot_app_ids(event)

    max_id = None
    try:
        if event.callback and event.callback.user:
            max_id = event.callback.user.user_id
    except Exception:
        pass

    if payload.section == "request_id":
        await _request_id(event, max_id)
        return

    if payload.section == "my_tests":
        await _show_student_tests(event, bot_username, bot_id, max_id)


async def _request_id(event, max_id):
    if not max_id:
        await event.edit(
            text="Не удалось получить ID. Напишите команду /id в чат.",
            attachments=[build_back_to_student().as_markup()],
        )
        return

    # upsert
    try:
        from_user = event.callback.user
        parts = [getattr(from_user, "first_name", None), getattr(from_user, "last_name", None)]
        name = " ".join(p for p in parts if p) or (getattr(from_user, "username", None) or f"user_{max_id}")
    except Exception:
        name = f"user_{max_id}"

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

    pending_fio.add(max_id)
    extra = (
        "ФИО уже сохранено. Чтобы изменить — напишите заново: Фамилия Имя"
        if has_fio
        else "Напишите следующим сообщением Фамилию и Имя\nНапример: Иванов Иван"
    )
    await event.edit(
        text=(
            f"Ваш ID: {max_id}\n\n"
            f"Передайте его преподавателю, чтобы он добавил вас в класс.\n\n"
            f"{extra}"
        ),
        attachments=[build_back_to_student().as_markup()],
    )


async def _show_student_tests(event, bot_username, bot_id, max_id):
    if not max_id:
        await event.edit(
            text="Не удалось определить пользователя.",
            attachments=[build_back_to_student().as_markup()],
        )
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.max_id == max_id).first()
        if not user:
            await event.edit(
                text="Пока нет результатов.\nПройдите тест по коду от учителя.",
                attachments=[build_student_history_keyboard(bot_username, bot_id).as_markup()],
            )
            return

        attempts = (
            db.query(TestAttempt)
            .filter(
                TestAttempt.student_id == user.id,
                TestAttempt.score.isnot(None),
            )
            .order_by(TestAttempt.id.desc())
            .limit(5)
            .all()
        )
        if not attempts:
            text = "Пока нет сданных тестов.\nПройдите тест по коду от учителя."
        else:
            lines = ["Последние результаты:\n"]
            for i, att in enumerate(attempts, 1):
                test = db.query(Test).filter(Test.id == att.test_id).first()
                title = (test.title if test else None) or "Без названия"
                total = db.query(Question).filter(Question.test_id == att.test_id).count()
                if total and att.score is not None:
                    pct = round(att.score / total * 100)
                    lines.append(f"{i}. {title} — {att.score}/{total} ({pct}%)")
                else:
                    lines.append(f"{i}. {title} — {att.score}")
            text = "\n".join(lines)

        await event.edit(
            text=text,
            attachments=[build_student_history_keyboard(bot_username, bot_id).as_markup()],
        )
    finally:
        db.close()


@router.message_callback(BackPayload.filter())
async def on_back(event: MessageCallback, payload: BackPayload):
    await event.answer()
    bot_username, bot_id = _bot_app_ids(event)

    if payload.to == "roles":
        await event.edit(
            text=WELCOME_TEXT,
            attachments=[build_role_keyboard().as_markup()],
        )
    elif payload.to == "teacher":
        await event.edit(
            text=TEACHER_TEXT,
            attachments=[build_teacher_keyboard(bot_username, bot_id).as_markup()],
        )
    elif payload.to == "student":
        await event.edit(
            text=STUDENT_TEXT,
            attachments=[build_student_keyboard(bot_username, bot_id).as_markup()],
        )
