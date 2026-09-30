# Синапс

Образовательное мини-приложение и бот для мессенджера **MAX**: тесты с ИИ, журнал класса, запланированные контрольные, умные конспекты.

Хакатон MAX · трек образовательных решений.

---

## Возможности

| Роль | Функции |
|------|---------|
| **Учитель** | Класс (журнал), создание тестов (GigaChat), черновики, публикация по коду/QR, уведомления, аналитика, анонсы запланированных тестов |
| **Ученик** | Регистрация (ФИО), поиск теста по коду, история, запланированные + материалы, умный конспект |

- Один класс на учителя (MVP)
- Можно добавить **себя** учеником для демо с одного аккаунта
- Уведомления в MAX при публикации теста и при создании анонса (+ напоминание за день)

---

## Стек

- **Backend:** FastAPI, SQLAlchemy, PostgreSQL  
- **Frontend:** статический HTML/JS (мини-приложение MAX)  
- **Бот:** maxapi (polling)  
- **ИИ:** GigaChat  
- **Деплой:** Railway / Docker Compose  

---

## Быстрый старт (Docker)

### 1. Переменные окружения

```bash
cp .env.example .env
# Заполните его
```

### 2. Запуск

```bash
docker compose up --build -d
```

Сервисы:

| Сервис | URL / роль |
|--------|------------|
| `backend` | http://localhost:8000 — API + мини-приложение |
| `bot` | long-polling бота MAX |
| `postgres` | localhost:5432 |

Остановка:

```bash
docker compose down
```

Данные БД сохраняются в volume `postgres_data`.

### 3. Миграции

Таблицы создаются при старте backend (`Base.metadata.create_all`).

Дополнительно для уже существующей БД (например Railway) выполните SQL из файла:

```bash
psql "$DATABASE_URL" -f migration_scheduled.sql
```

Файл добавляет:

- колонку `tests.subject`
- таблицу `scheduled_tests`

В Docker Compose тот же SQL подключается в `docker-entrypoint-initdb.d` при **первом** создании volume.

---

## Локальный запуск без Docker

### PostgreSQL

```bash
docker compose up postgres -d
```

или свой инстанс Postgres и `DATABASE_URL` в `.env`.

### Python

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
```

### Backend

```bash
export PYTHONPATH=.
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Бот

```bash
export PYTHONPATH=.
python -m max_bot.main
```

---

## Структура проекта

```
├── backend/           # FastAPI: API, модели, GigaChat, auth MAX
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   └── gigachat_services.py
├── frontend/          # Мини-приложение (HTML/CSS/JS)
├── max_bot/           # Бот MAX
├── migration_scheduled.sql
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `MAX_TOKEN` | Токен бота MAX (обязательно) |
| `MAX_BOT_USERNAME` | Username бота без `@` (диплинки, QR) |
| `APP_URL` | Публичный URL мини-приложения |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/db` |
| `GIGACHAT_TOKEN` | Токен GigaChat для генерации |
| `POSTGRES_*` | Для Compose (user / password / db) |

---

## Мини-приложение MAX

1. В кабинете бота MAX укажите URL backend (`APP_URL`) как Web App.  
2. Пользователь открывает приложение **из бота** (нужен `initData`).  
3. Ученик: **Регистрация** в боте (ФИО) → полное меню.  
4. Учитель: **Журнал** → создать класс → добавить учеников по MAX ID.

Демо с одного аккаунта: в журнале добавьте **свой** MAX ID как ученика — увидите запланированные тесты и в роли ученика.

---

## Основные экраны

| Путь | Кто | Описание |
|------|-----|----------|
| `/` | — | Выбор роли |
| `/teacher_page` | учитель | Меню |
| `/class_page` | учитель | Журнал класса |
| `/teacher.html` | учитель | Создание / редактирование теста |
| `/my_tests` | учитель | Черновики и опубликованные |
| `/scheduled_page` | учитель | Анонсы тестов |
| `/student_page` | ученик | Меню (после регистрации) |
| `/student.html` | ученик | Вход по коду |
| `/student_scheduled` | ученик | Запланированные + материалы |
| `/smart_notes.html` | ученик | Умный конспект |

---

## API (кратко)

- `POST /tests/save` — сохранить тест / черновик  
- `PUT /api/teacher/tests/{id}` — редактировать черновик  
- `GET/POST /api/scheduled` — анонсы (учитель)  
- `GET /api/student/scheduled` — анонсы ученика  
- `GET /api/scheduled/{id}/materials` — скачать материалы  
- `GET /auth/me` — текущий пользователь MAX  

Интерактивная документация: http://localhost:8000/docs  

---

## Railway

1. Создайте Postgres и сервисы **backend** + **bot** (один репозиторий, разные start-команды).  
2. Backend: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`  
3. Bot: `python -m max_bot.main`  
4. В Variables задайте `DATABASE_URL`, `MAX_TOKEN`, `GIGACHAT_TOKEN`, `APP_URL`, `MAX_BOT_USERNAME`.  
5. Один раз выполните `migration_scheduled.sql` в Postgres.  

`PYTHONPATH` должен указывать на корень репозитория.

---

## Важно

- Генерация тестов и конспектов выполняется **ИИ** — ответы могут содержать ошибки, проверяйте перед публикацией.  
- Уведомления в MAX доставляются только пользователям, которые хотя бы раз написали боту (`/start` или регистрация).  

---

## Лицензия

Проект для хакатона MAX. Используйте и дорабатывайте свободно в рамках условий хакатона.
