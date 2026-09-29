import os

from dotenv import load_dotenv

load_dotenv()


def _int_or_none(value):
    return int(value) if value not in (None, "") else None


class Settings:

    max_api_key: str = os.getenv("MAX_TOKEN", "")
    app_url: str | None = os.getenv("APP_URL")
    max_bot_username: str | None = os.getenv("MAX_BOT_USERNAME") or os.getenv("MAX_BOT_NAME")

    # Не используются напрямую в коде ниже, но могут понадобиться
    # для других частей проекта — не должны падать, если их нет в .env.
    max_bot_id: int | None = _int_or_none(os.getenv("MAX_BOT_ID"))
    contact_id: int | None = _int_or_none(os.getenv("CONTACT_ID"))


settings = Settings()

if not settings.max_api_key:
    raise RuntimeError(
        "Не задан MAX_TOKEN в .env — без него бот не сможет подключиться к MAX."
    )
