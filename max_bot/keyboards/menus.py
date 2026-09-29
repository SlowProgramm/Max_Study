"""
Тексты и клавиатуры главного меню MAX Study.

OpenAppButton: у бота один URL мини-приложения; нужный экран задаётся
через payload → start_param → роутинг на фронте (index.html).
"""

from maxapi.filters.callback_payload import CallbackPayload
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.attachments.buttons.open_app_button import OpenAppButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


# ── payload-адреса экранов мини-приложения ────────────────────────────────
APP_PAGE_TEACHER_CLASS = "teacher_class"
APP_PAGE_TEACHER_CREATE_TEST = "teacher_create_test"
APP_PAGE_TEACHER_MY_TESTS = "teacher_my_tests"
APP_PAGE_TEACHER_ANALYTICS = "teacher_analytics"
APP_PAGE_TEACHER_TEST = "teacher_test"  # + _<id>
APP_PAGE_STUDENT_TAKE_TEST = "student_take_test"
APP_PAGE_STUDENT_HISTORY = "student_history"
APP_PAGE_SMART_NOTES = "smart_notes"
APP_PAGE_JOURNAL_TEST = "journal_test"  # + _<id>


# ── callback payloads ─────────────────────────────────────────────────────
class RolePayload(CallbackPayload, prefix="role"):
    role: str  # teacher | student


class TeacherSectionPayload(CallbackPayload, prefix="tch_sec"):
    section: str  # class | my_tests


class StudentSectionPayload(CallbackPayload, prefix="stu_sec"):
    section: str  # my_tests | request_id


class BackPayload(CallbackPayload, prefix="back"):
    to: str  # roles | teacher | student


# ── тексты ────────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "Добро пожаловать в MAX Study!\n\n"
    "Тесты, проверка знаний и умные конспекты.\n\n"
    "Выберите роль:"
)

TEACHER_TEXT = (
    "Режим учителя\n\n"
    "Класс, тесты и аналитика — выберите раздел:"
)

STUDENT_TEXT = (
    "Режим ученика\n\n"
    "Проходите тесты, смотрите результаты и готовьтесь с умным конспектом."
)


def build_role_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(text="Я учитель", payload=RolePayload(role="teacher").pack()),
        CallbackButton(text="Я ученик", payload=RolePayload(role="student").pack()),
    )
    return kb


def build_teacher_keyboard(bot_username: str, bot_id: int) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(
            text="Мой класс",
            payload=TeacherSectionPayload(section="class").pack(),
        )
    )
    kb.row(
        OpenAppButton(
            text="Создать тест",
            web_app=bot_username,
            contact_id=bot_id,
            payload=APP_PAGE_TEACHER_CREATE_TEST,
        )
    )
    kb.row(
        CallbackButton(
            text="Мои тесты",
            payload=TeacherSectionPayload(section="my_tests").pack(),
        )
    )
    kb.row(
        OpenAppButton(
            text="Аналитика",
            web_app=bot_username,
            contact_id=bot_id,
            payload=APP_PAGE_TEACHER_ANALYTICS,
        )
    )
    kb.row(
        CallbackButton(text="Назад", payload=BackPayload(to="roles").pack())
    )
    return kb


def build_student_keyboard(bot_username: str, bot_id: int) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(
        OpenAppButton(
            text="Пройти тест",
            web_app=bot_username,
            contact_id=bot_id,
            payload=APP_PAGE_STUDENT_TAKE_TEST,
        )
    )
    kb.row(
        CallbackButton(
            text="Мои тесты",
            payload=StudentSectionPayload(section="my_tests").pack(),
        )
    )
    kb.row(
        OpenAppButton(
            text="Умный конспект",
            web_app=bot_username,
            contact_id=bot_id,
            payload=APP_PAGE_SMART_NOTES,
        )
    )
    kb.row(
        CallbackButton(
            text="Запросить ID",
            payload=StudentSectionPayload(section="request_id").pack(),
        )
    )
    kb.row(
        CallbackButton(text="Назад", payload=BackPayload(to="roles").pack())
    )
    return kb


def build_back_to_teacher() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="В меню учителя", payload=BackPayload(to="teacher").pack()))
    return kb


def build_back_to_student() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="В меню ученика", payload=BackPayload(to="student").pack()))
    return kb


def build_teacher_tests_keyboard(
    bot_username: str,
    bot_id: int,
    tests: list[dict],
) -> InlineKeyboardBuilder:
    """tests: [{id, title}, ...] — до 3 последних + «Все тесты»."""
    kb = InlineKeyboardBuilder()
    for t in tests[:3]:
        title = (t.get("title") or "Без названия")[:40]
        kb.row(
            OpenAppButton(
                text=title,
                web_app=bot_username,
                contact_id=bot_id,
                payload=f"{APP_PAGE_TEACHER_TEST}_{t['id']}",
            )
        )
    kb.row(
        OpenAppButton(
            text="Посмотреть все тесты",
            web_app=bot_username,
            contact_id=bot_id,
            payload=APP_PAGE_TEACHER_MY_TESTS,
        )
    )
    kb.row(CallbackButton(text="В меню учителя", payload=BackPayload(to="teacher").pack()))
    return kb


def build_student_history_keyboard(
    bot_username: str,
    bot_id: int,
) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(
        OpenAppButton(
            text="Подробнее (все результаты)",
            web_app=bot_username,
            contact_id=bot_id,
            payload=APP_PAGE_STUDENT_HISTORY,
        )
    )
    kb.row(CallbackButton(text="В меню ученика", payload=BackPayload(to="student").pack()))
    return kb


def build_class_detail_keyboard(
    bot_username: str,
    bot_id: int,
    test_id: int | None,
) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    if test_id:
        kb.row(
            OpenAppButton(
                text="Подробнее",
                web_app=bot_username,
                contact_id=bot_id,
                payload=f"{APP_PAGE_JOURNAL_TEST}_{test_id}",
            )
        )
    kb.row(
        OpenAppButton(
            text="Открыть класс",
            web_app=bot_username,
            contact_id=bot_id,
            payload=APP_PAGE_TEACHER_CLASS,
        )
    )
    kb.row(CallbackButton(text="В меню учителя", payload=BackPayload(to="teacher").pack()))
    return kb
