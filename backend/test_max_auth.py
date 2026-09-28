"""
Запуск из корня проекта:  python -m unittest backend.test_max_auth -v
"""

import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import quote

from backend.max_auth import InitDataError, display_name, validate_init_data

BOT_TOKEN = "test-bot-token-123"


def sign(fields: dict, token: str = BOT_TOKEN) -> str:
    """Собирает initData так, как это делает MAX (по шагам из документации)."""

    launch = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, launch.encode(), hashlib.sha256).hexdigest()

    parts = [f"{k}={quote(str(v), safe='')}" for k, v in fields.items()]
    parts.append(f"hash={digest}")
    return "&".join(parts)


def make_fields(user=None, auth_date=None, **extra) -> dict:
    user = user or {"id": 67890, "first_name": "Max", "last_name": "User",
                    "username": "maxuser", "language_code": "ru", "photo_url": None}
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "4c0ab423-342b-4e45-aea4-2747dbc500cd",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
    }
    fields.update(extra)
    return fields


class ValidateInitDataTests(unittest.TestCase):

    def test_valid(self):
        data = validate_init_data(sign(make_fields()), BOT_TOKEN)
        self.assertEqual(data["user"]["id"], 67890)

    def test_start_param_is_returned(self):
        data = validate_init_data(
            sign(make_fields(start_param="teacher_class")), BOT_TOKEN
        )
        self.assertEqual(data["start_param"], "teacher_class")

    def test_wrong_token(self):
        with self.assertRaises(InitDataError) as ctx:
            validate_init_data(sign(make_fields()), "another-token")
        self.assertEqual(ctx.exception.code, "bad_signature")

    def test_tampered_user_id(self):
        # Главная угроза: подменить id на чужой, оставив старую подпись.
        good = sign(make_fields())
        evil_user = quote(json.dumps({"id": 1, "username": "victim"},
                                     separators=(",", ":")), safe="")
        tampered = "&".join(
            f"user={evil_user}" if p.startswith("user=") else p
            for p in good.split("&")
        )
        with self.assertRaises(InitDataError) as ctx:
            validate_init_data(tampered, BOT_TOKEN)
        self.assertEqual(ctx.exception.code, "bad_signature")

    def test_missing_hash(self):
        no_hash = "&".join(p for p in sign(make_fields()).split("&")
                           if not p.startswith("hash="))
        with self.assertRaises(InitDataError) as ctx:
            validate_init_data(no_hash, BOT_TOKEN)
        self.assertEqual(ctx.exception.code, "no_hash")

    def test_duplicate_hash(self):
        good = sign(make_fields())
        with self.assertRaises(InitDataError) as ctx:
            validate_init_data(good + "&hash=abc", BOT_TOKEN)
        self.assertEqual(ctx.exception.code, "malformed")

    def test_duplicate_param_smuggling(self):
        good = sign(make_fields())
        with self.assertRaises(InitDataError):
            validate_init_data(good + "&user=%7B%22id%22%3A1%7D", BOT_TOKEN)

    def test_empty(self):
        for value in ("", None):
            with self.assertRaises(InitDataError) as ctx:
                validate_init_data(value, BOT_TOKEN)
            self.assertEqual(ctx.exception.code, "missing")

    def test_no_server_token(self):
        with self.assertRaises(InitDataError) as ctx:
            validate_init_data(sign(make_fields()), "")
        self.assertEqual(ctx.exception.code, "no_token")

    def test_garbage(self):
        with self.assertRaises(InitDataError):
            validate_init_data("не initData вообще", BOT_TOKEN)

    def test_expired(self):
        old = int(time.time()) - 3 * 86400
        with self.assertRaises(InitDataError) as ctx:
            validate_init_data(sign(make_fields(auth_date=old)), BOT_TOKEN)
        self.assertEqual(ctx.exception.code, "expired")

    def test_expiry_can_be_disabled(self):
        old = int(time.time()) - 3 * 86400
        data = validate_init_data(
            sign(make_fields(auth_date=old)), BOT_TOKEN, max_age_seconds=None
        )
        self.assertEqual(data["user"]["id"], 67890)

    def test_unicode_and_special_chars(self):
        user = {"id": 42, "first_name": "Мария", "last_name": "Иванова+О'Нил=1&2",
                "username": None}
        data = validate_init_data(sign(make_fields(user=user)), BOT_TOKEN)
        self.assertEqual(data["user"]["first_name"], "Мария")
        self.assertEqual(data["user"]["last_name"], "Иванова+О'Нил=1&2")

    def test_big_max_id(self):
        # max_id в БД — BigInteger; проверим, что большие id не ломаются.
        user = {"id": 9_007_199_254_740_993, "username": "big"}
        data = validate_init_data(sign(make_fields(user=user)), BOT_TOKEN)
        self.assertEqual(data["user"]["id"], 9_007_199_254_740_993)


class DisplayNameTests(unittest.TestCase):

    def test_username_wins(self):
        self.assertEqual(display_name({"id": 1, "username": "ivan",
                                       "first_name": "Иван"}), "ivan")

    def test_null_username_falls_back_to_name(self):
        self.assertEqual(display_name({"id": 1, "username": None,
                                       "first_name": "Иван",
                                       "last_name": "Петров"}), "Иван Петров")

    def test_only_first_name(self):
        self.assertEqual(display_name({"id": 1, "username": None,
                                       "first_name": "Иван",
                                       "last_name": None}), "Иван")

    def test_nothing_at_all(self):
        self.assertEqual(display_name({"id": 555, "username": None}), "user555")

    def test_blank_username(self):
        self.assertEqual(display_name({"id": 7, "username": "  ",
                                       "first_name": "Оля"}), "Оля")


if __name__ == "__main__":
    unittest.main()
