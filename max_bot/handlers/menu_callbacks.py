import logging

from maxapi import Router
from maxapi.types.updates.message_callback import MessageCallback

from max_bot.keyboards.menus import (
    STUDENT_TESTS_TEXT,
    STUDENT_TEXT,
    TEACHER_TEXT,
    WELCOME_TEXT,
    BackPayload,
    MyTestsPayload,
    RolePayload,
    StudentSectionPayload,
    build_role_keyboard,
    build_student_root_keyboard,
    build_student_tests_keyboard,
    build_teacher_keyboard,
)

router = Router()


def _bot_app_ids(event: MessageCallback) -> tuple[str, int]:
    """username и id бота — нужны, чтобы собрать кнопку OpenAppButton."""

    me = event.bot.me
    return me.username, me.user_id


@router.message_callback(RolePayload.filter())
async def on_role_selected(event: MessageCallback, payload: RolePayload):

    logging.info("Выбрана роль: %s", payload.role)

    await event.answer()

    bot_username, bot_id = _bot_app_ids(event)

    if payload.role == "teacher":
        await event.edit(
            text=TEACHER_TEXT,
            attachments=[
                build_teacher_keyboard(bot_username, bot_id).as_markup()
            ],
        )
    else:
        await event.edit(
            text=STUDENT_TEXT,
            attachments=[
                build_student_root_keyboard(bot_username, bot_id).as_markup()
            ],
        )


@router.message_callback(StudentSectionPayload.filter())
async def on_student_section(
    event: MessageCallback,
    payload: StudentSectionPayload,
):

    await event.answer()

    if payload.section != "tests":
        return

    bot_username, bot_id = _bot_app_ids(event)

    await event.edit(
        text=STUDENT_TESTS_TEXT,
        attachments=[
            build_student_tests_keyboard(bot_username, bot_id).as_markup()
        ],
    )


@router.message_callback(MyTestsPayload.filter())
async def on_my_tests(event: MessageCallback, payload: MyTestsPayload):
    """
    «Мои тесты». Пока заглушка: список тестов и результатов ученика
    захардкожен. В будущем — заменить на реальный запрос к backend
    (например GET /students/{id}/tests).
    """

    await event.answer()

    stub_results = (
        "📊 Мои тесты\n\n"
        "1. «Дроби и проценты» — 8/10 (80%)\n"
        "2. «История России, XIX век» — 6/10 (60%)\n"
        "3. «Неправильные глаголы (англ.)» — ещё не пройден\n\n"
        "Это тестовые данные — здесь появится реальная статистика "
        "по вашим попыткам."
    )

    bot_username, bot_id = _bot_app_ids(event)

    await event.edit(
        text=stub_results,
        attachments=[
            build_student_tests_keyboard(bot_username, bot_id).as_markup()
        ],
    )


@router.message_callback(BackPayload.filter())
async def on_back(event: MessageCallback, payload: BackPayload):

    await event.answer()

    if payload.to == "roles":
        await event.edit(
            text=WELCOME_TEXT,
            attachments=[build_role_keyboard().as_markup()],
        )
        return

    bot_username, bot_id = _bot_app_ids(event)

    if payload.to == "student_root":
        await event.edit(
            text=STUDENT_TEXT,
            attachments=[
                build_student_root_keyboard(bot_username, bot_id).as_markup()
            ],
        )
    elif payload.to == "student_tests":
        await event.edit(
            text=STUDENT_TESTS_TEXT,
            attachments=[
                build_student_tests_keyboard(bot_username, bot_id).as_markup()
            ],
        )
