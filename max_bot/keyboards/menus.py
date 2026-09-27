"""
Тексты и клавиатуры главного меню MAX Study.

Важно про кнопки мини-приложения (OpenAppButton):
у бота есть только ОДИН адрес мини-приложения, зарегистрированный в
MasterBot, и передать произвольную ссылку через код нельзя (см. также
комментарий в app_keyboard.py). Чтобы кнопка вела на нужный экран внутри
приложения (страницу учителя, страницу теста и т.д.), ей задаётся свой
`payload` — это значение прокидывается в initData мини-приложения, и уже
сам фронтенд должен прочитать его (например, через `start_param`
в MAX Bridge) и открыть соответствующую страницу/раздел.

Значения APP_PAGE_* — это как раз такие "адреса" экранов, которые нужно
будет обработать на стороне фронтенда мини-приложения.
"""

from maxapi.filters.callback_payload import CallbackPayload
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.attachments.buttons.open_app_button import OpenAppButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


# ── "адреса" экранов мини-приложения, передаются через payload ────────────
APP_PAGE_TEACHER_CLASS = "teacher_class"
APP_PAGE_TEACHER_CREATE_TEST = "teacher_create_test"
APP_PAGE_STUDENT_TAKE_TEST = "student_take_test"
APP_PAGE_STUDENT_CREATE_TEST = "student_create_test"
APP_PAGE_SMART_NOTES = "smart_notes"


# ── payload-классы для callback-кнопок (навигация внутри чата) ────────────
class RolePayload(CallbackPayload, prefix="role"):
    """Выбор роли на старте: учитель или ученик."""

    role: str  # "teacher" | "student"


class StudentSectionPayload(CallbackPayload, prefix="stu_section"):
    """Выбор раздела в меню ученика."""

    section: str  # "tests"


class MyTestsPayload(CallbackPayload, prefix="my_tests"):
    """Кнопка «Мои тесты»."""


class BackPayload(CallbackPayload, prefix="back"):
    """Кнопка «Назад» с указанием, куда возвращаемся."""

    to: str  # "roles" | "student_root" | "student_tests"


# ── тексты экранов (заглушки, можно заменить на боевые) ────────────────────
WELCOME_TEXT = (
    "👋 Добро пожаловать в MAX Study!\n\n"
    "Это учебный помощник: тесты, проверка знаний и умные конспекты "
    "прямо в MAX.\n\n"
    "Выберите, кто вы:"
)

TEACHER_TEXT = (
    "👩‍🏫 Режим учителя\n\n"
    "Здесь можно посмотреть свой класс и результаты учеников, "
    "а также создать новый тест."
)

STUDENT_TEXT = (
    "🎓 Режим ученика\n\n"
    "Проходите тесты, следите за своими результатами и пользуйтесь "
    "умным конспектом для подготовки."
)

STUDENT_TESTS_TEXT = (
    "📝 Тесты\n\n"
    "Пройдите тест по коду от учителя, посмотрите свои результаты "
    "или создайте собственный тест."
)


def build_role_keyboard() -> InlineKeyboardBuilder:
    """/start — выбор роли."""

    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(
            text="Я учитель",
            payload=RolePayload(role="teacher").pack(),
        ),
        CallbackButton(
            text="Я ученик",
            payload=RolePayload(role="student").pack(),
        ),
    )
    return kb


def build_teacher_keyboard(
    bot_username: str,
    bot_id: int,
) -> InlineKeyboardBuilder:
    """Меню учителя: «Мой класс» и «Создать тест»."""

    kb = InlineKeyboardBuilder()
    kb.row(
        OpenAppButton(
            text="Мой класс",
            web_app=bot_username,
            contact_id=bot_id,
            payload=APP_PAGE_TEACHER_CLASS,
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
            text="← Назад",
            payload=BackPayload(to="roles").pack(),
        )
    )
    return kb


def build_student_root_keyboard(
    bot_username: str,
    bot_id: int,
) -> InlineKeyboardBuilder:
    """Меню ученика: «Тесты» и «Умный конспект»."""

    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(
            text="Тесты",
            payload=StudentSectionPayload(section="tests").pack(),
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
            text="← Назад",
            payload=BackPayload(to="roles").pack(),
        )
    )
    return kb


def build_student_tests_keyboard(
    bot_username: str,
    bot_id: int,
) -> InlineKeyboardBuilder:
    """Подменю «Тесты»: пройти / мои / создать."""

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
            payload=MyTestsPayload().pack(),
        )
    )
    kb.row(
        OpenAppButton(
            text="Создать тест",
            web_app=bot_username,
            contact_id=bot_id,
            payload=APP_PAGE_STUDENT_CREATE_TEST,
        )
    )
    kb.row(
        CallbackButton(
            text="← Назад",
            payload=BackPayload(to="student_root").pack(),
        )
    )
    return kb
