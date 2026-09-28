"""
Проверка подлинности данных мини-приложения MAX (initData).

Алгоритм — из официальной документации:
https://dev.max.ru/docs/webapps/validation

Идея: user.id можно доверять ТОЛЬКО если подпись initData сошлась.
Всё, что браузер прислал сам (например, max_id в теле запроса), подделывается.

Модуль намеренно не зависит от FastAPI/SQLAlchemy — так его можно
тестировать отдельно: python -m unittest backend.test_max_auth
"""

import hashlib
import hmac
import json
import os
import time
from urllib.parse import unquote

from dotenv import load_dotenv

load_dotenv()

# Насколько «свежим» должен быть initData (auth_date). По умолчанию 24 часа.
DEFAULT_MAX_AGE = int(os.getenv("MAX_INITDATA_MAX_AGE", "86400"))


class InitDataError(Exception):
    """initData не прошёл проверку. code — машинное имя причины."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int | None = DEFAULT_MAX_AGE,
) -> dict:
    """
    Проверяет подпись initData и возвращает разобранные данные:
    {"user": {...}, "start_param": str | None, "auth_date": int, "fields": {...}}

    Бросает InitDataError, если данные пустые, подделаны или устарели.
    """

    if not init_data:
        raise InitDataError("missing", "initData не передан")

    if not bot_token:
        raise InitDataError("no_token", "На сервере не задан MAX_TOKEN")

    # 1. key=value&key=value  →  [(key, value)], значения URL-декодируем.
    #    decodeURIComponent в JS не превращает '+' в пробел — поэтому unquote,
    #    а не unquote_plus. partition по первому '=' — как в разборе значений.
    pairs: list[tuple[str, str]] = []
    for chunk in init_data.split("&"):
        key, sep, value = chunk.partition("=")
        if not sep or not key:
            raise InitDataError("malformed", "initData имеет неверный формат")
        pairs.append((key, unquote(value)))

    # 2. Ни один ключ не должен повторяться (защита от подмены параметров),
    #    hash должен быть ровно один.
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise InitDataError("malformed", "В initData повторяются параметры")

    fields = dict(pairs)
    original_hash = fields.pop("hash", None)
    if not original_hash:
        raise InitDataError("no_hash", "В initData нет подписи (hash)")

    # 3. Сортировка по ключам a→z, склейка через \n (без hash).
    launch_params = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))

    # 4. secret_key = HMAC_SHA256(key="WebAppData", msg=BOT_TOKEN)
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()

    # 5. hash = hex(HMAC_SHA256(key=secret_key, msg=launch_params))
    calculated = hmac.new(
        secret_key, launch_params.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(
        calculated.encode("ascii"), original_hash.encode("utf-8")
    ):
        raise InitDataError("bad_signature", "Подпись initData не совпала")

    # 6. Подпись верна — теперь можно разбирать содержимое.
    try:
        auth_date = int(fields.get("auth_date", ""))
    except ValueError:
        raise InitDataError("malformed", "В initData нет корректного auth_date")

    now = int(time.time())
    if max_age_seconds is not None and now - auth_date > max_age_seconds:
        raise InitDataError(
            "expired", "initData устарел — закройте и откройте мини-приложение заново"
        )

    try:
        user = json.loads(fields["user"])
        user_id = int(user["id"])
    except (KeyError, ValueError, TypeError):
        raise InitDataError("no_user", "В initData нет данных пользователя")

    user["id"] = user_id

    return {
        "user": user,
        "start_param": fields.get("start_param"),
        "auth_date": auth_date,
        "fields": fields,
    }


def display_name(user: dict) -> str:
    """
    В MAX username бывает null (в примере из документации так и есть),
    а в таблице users колонка username — NOT NULL. Поэтому запасной вариант:
    username → имя + фамилия → user<id>.
    """

    username = (user.get("username") or "").strip()
    if username:
        return username

    full_name = " ".join(
        part.strip()
        for part in (user.get("first_name") or "", user.get("last_name") or "")
        if part and part.strip()
    )
    if full_name:
        return full_name

    return f"user{user['id']}"
