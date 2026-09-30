from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload, load_only
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
# from typing import Literal, Optional
from backend.schemas import (
    # ... ваши существующие импорты ...
    StudentOut,
    ClassOut,
    CreateClassIn,
    AddStudentIn,
    AttemptHistoryItem,
    JournalTestItem,
    JournalStudentScore,
    QuestionStat,
    TestAnalytics,
    StudentAttemptDetail,
    GradebookResponse,
    GradebookStudent,
    GradebookScore,
    DraftTestItem,
    NotifyTestRequest,
    TestEntryInfo,
    ScheduledTestCreate,
    ScheduledTestOut,
    UpdateDraftRequest,
)
from backend.models import Class, ClassMember, TestAttempt, ScheduledTest
from sqlalchemy import func
from datetime import datetime, timedelta, date
import random
import string
import os
import fitz  # pymupdf
from typing import Literal, Optional
from backend.database import SessionLocal, engine, Base
from backend import models
from backend.models import StudentAnswer, Test, Question, AnswerOption, User
from backend.gigachat_services import (
    generate_quiz_by_topic,
    generate_quiz_by_text,
    create_custom_quiz,
    generate_notes_by_topic,
    generate_notes_by_text,
)
from backend.max_auth import validate_init_data, display_name, InitDataError
from backend.schemas import (
    TestCreate,
    TestResponse,
    QuestionCreate,
    QuestionResponse,
    AnswerOptionCreate,
    AnswerOptionResponse,
    TestPublic,
    SaveTestRequest,
    SubmitTestRequest,
    GeneratedTestResponse,
    UserCreate,
    UserResponse,
    UserAuth,
    StartTestRequest,
)


# ─── Модели запросов ─────────────────────────────

class GenerateTestRequest(BaseModel):
    mode: Literal["topic", "text", "custom"]
    topic: Optional[str] = None
    content: Optional[str] = None
    question_count: int = 5
    questions: Optional[list] = None


class MaxAuthRequest(BaseModel):
    init_data: str


class GenerateNotesRequest(BaseModel):
    mode: str  # "topic" или "text"
    topic: str | None = None
    content: str | None = None


# ─── Приложение ─────────────────────────────────

app = FastAPI(title="Синапс")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

print("DATABASE_URL:", os.getenv("DATABASE_URL"))
print("Tables before create_all:", list(Base.metadata.tables.keys()))
Base.metadata.create_all(bind=engine)
print("Tables after create_all:", list(Base.metadata.tables.keys()))

# ─── Вспомогательные ────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def short_name(username: str | None) -> str:
    """
    'Иван Иванов' / 'Иванов Иван' → 'Иванов И.'
    'гриша' / одно слово → 'Гриша' (с заглавной)
    """
    parts = [p for p in (username or "").strip().split() if p]
    if not parts:
        return "—"
    if len(parts) >= 2:
        # Если передали «Фамилия Имя» — фамилия первая
        last = parts[0]
        first = parts[1]
        return f"{last.capitalize()} {first[0].upper()}."
    # одно слово — просто имя с заглавной
    return parts[0][:1].upper() + parts[0][1:]


def display_student_name(user: User | None) -> str:
    """Предпочитает full_name (ФИО из /id), иначе username из MAX."""
    if not user:
        return "—"
    name = (getattr(user, "full_name", None) or user.username or "").strip()
    return short_name(name) if name else "—"


def read_cheat_stats(db: Session, attempt_id: int) -> tuple[int, int]:
    """Читает leave_count/hidden_seconds. Если колонок нет — (0, 0)."""
    try:
        from sqlalchemy import text as sa_text
        row = db.execute(
            sa_text("SELECT leave_count, hidden_seconds FROM test_attempts WHERE id = :id"),
            {"id": attempt_id},
        ).first()
        if row:
            return (row[0] or 0), (row[1] or 0)
    except Exception:
        db.rollback()
    return 0, 0



def compute_time_limit_seconds(minutes: int | None, seconds: int | None) -> int | None:
    m = minutes or 0
    s = seconds or 0
    total = m * 60 + s
    return total if total > 0 else None


def resolve_time_limit_seconds(test) -> int | None:
    """Итоговое время в секундах (поддержка legacy time_limit_minutes)."""
    if getattr(test, "time_limit_seconds", None):
        return test.time_limit_seconds
    mins = getattr(test, "time_limit_minutes", None)
    if mins and mins > 0:
        return mins * 60
    return None


def send_max_message(
    user_max_id: int,
    text: str,
    button_url: str | None = None,
    button_text: str = "Открыть тест",
) -> tuple[bool, str]:
    """
    Отправка сообщения ученику через MAX Bot API.
    Возвращает (ok, error_message).
    Токен: MAX_TOKEN (тот же, что у бота).
    """
    import httpx
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    token = (os.getenv("MAX_TOKEN") or "").strip()
    if not token:
        msg = "MAX_TOKEN не задан в переменных окружения Railway"
        print("MAX notify:", msg)
        return False, msg

    def _post(payload: dict) -> tuple[bool, str]:
        # verify=False: на Railway/многих VPS нет корня Минцифры,
        # из-за этого SSL: CERTIFICATE_VERIFY_FAILED к platform-api2.max.ru
        try:
            r = httpx.post(
                f"https://platform-api2.max.ru/messages?user_id={int(user_max_id)}",
                headers={
                    "Authorization": token,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
                verify=False,
            )
            if r.status_code == 200:
                return True, ""
            err = f"HTTP {r.status_code}: {r.text[:400]}"
            print("MAX notify status:", err)
            return False, err
        except Exception as e:
            err = f"exception: {e}"
            print("MAX notify error:", err)
            return False, err

    # 1) С кнопкой-ссылкой (если есть)
    if button_url and str(button_url).startswith("http"):
        payload = {
            "text": text,
            "attachments": [{
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [[{
                        "type": "link",
                        "text": button_text,
                        "url": button_url,
                    }]]
                }
            }],
        }
        ok, err = _post(payload)
        if ok:
            return True, ""
        # fallback без кнопки — иногда API ругается на url
        print("MAX notify: retry without button for", user_max_id, err)
        ok2, err2 = _post({"text": text})
        return (ok2, err2 if not ok2 else "")

    ok, err = _post({"text": text})
    return ok, err



def bot_username() -> str:
    """Username бота без @ — для диплинков https://max.ru/<name>?startapp=..."""
    return (os.getenv("MAX_BOT_USERNAME") or os.getenv("MAX_BOT_NAME") or "").lstrip("@").strip()


def max_deep_link(start_payload: str) -> str | None:
    """
    Ссылка, которая открывает мини-приложение ВНУТРИ MAX.
    Формат: https://max.ru/<botName>?startapp=<payload>
    """
    name = bot_username()
    if not name:
        return None
    payload = (start_payload or "").strip()
    if payload:
        return f"https://max.ru/{name}?startapp={payload}"
    return f"https://max.ru/{name}?startapp"


def resolve_app_base_url(request: Request | None = None) -> str:
    """
    Базовый URL мини-приложения — тот же host, что в QR.
    1) APP_URL из env (если задан)
    2) иначе origin из текущего HTTP-запроса (Railway / любой хост)
    """
    env = (os.getenv("APP_URL") or "").rstrip("/")
    if env:
        return env
    if request is not None:
        # request.base_url: https://xxx.up.railway.app/
        return str(request.base_url).rstrip("/")
    return ""


def notify_students_about_test(
    db: Session,
    teacher_id: int,
    test,
    class_id: int | None = None,
    class_ids: list[int] | None = None,
    request: Request | None = None,
) -> dict:
    code = test.access_code
    # Диплинк MAX — открывает мини-приложение внутри MAX, не внешний браузер
    link = max_deep_link(f"test_{code}")
    if not link:
        # fallback: https origin мини-приложения (если username бота не задан)
        app_url = resolve_app_base_url(request)
        link = f"{app_url}/test_entry?code={code}" if app_url else None

    q = (
        db.query(User)
        .join(ClassMember, ClassMember.student_id == User.id)
        .join(Class, Class.id == ClassMember.class_id)
        .filter(Class.teacher_id == teacher_id)
    )
    # Приоритет: class_ids (список) > class_id (один) > все классы
    ids = None
    if class_ids:
        ids = [int(x) for x in class_ids if x is not None]
    elif class_id is not None:
        ids = [int(class_id)]
    if ids:
        q = q.filter(Class.id.in_(ids))
    students = q.distinct().all()

    time_s = resolve_time_limit_seconds(test)
    time_line = ""
    if time_s:
        mm, ss = divmod(time_s, 60)
        time_line = f"\nВремя: {mm} мин {ss} сек" if mm else f"\nВремя: {ss} сек"

    subject = getattr(test, "subject", None)
    subj_line = f"\nПредмет: {subject}" if subject else ""
    text = (
        f"Новый тест: {test.title or 'Без названия'}"
        f"{subj_line}"
        f"{time_line}"
        f"\nКод: {code}"
    )
    if link:
        text += f"\n{link}"

    sent, failed = 0, 0
    errors: list[str] = []
    token_ok = bool((os.getenv("MAX_TOKEN") or "").strip())
    for st in students:
        ok, err = send_max_message(st.max_id, text, button_url=link)
        if ok:
            sent += 1
        else:
            failed += 1
            # Не больше 5 деталей, чтобы ответ не раздувался
            if len(errors) < 5:
                errors.append(f"user {st.max_id}: {err or 'unknown'}")
    out = {
        "sent": sent,
        "failed": failed,
        "total": len(students),
        "link": link,
        "token_present": token_ok,
        "bot_username": bot_username() or None,
    }
    if errors:
        out["errors"] = errors
    if not token_ok:
        out["hint"] = "Добавьте MAX_TOKEN в Variables сервиса backend на Railway (тот же токен, что у бота)."
    elif failed and sent == 0:
        out["hint"] = (
            "Сообщения не доставлены. Частые причины: "
            "1) ученик ни разу не писал боту (/start или /id) — сначала пусть напишет; "
            "2) неверный MAX_TOKEN на Railway; "
            "3) смотрите errors и логи backend."
        )
    return out

def write_cheat_stats(db: Session, attempt_id: int, leave_count: int, hidden_seconds: int) -> None:
    try:
        from sqlalchemy import text as sa_text
        db.execute(
            sa_text(
                "UPDATE test_attempts SET leave_count = :lc, hidden_seconds = :hs WHERE id = :id"
            ),
            {"lc": leave_count or 0, "hs": hidden_seconds or 0, "id": attempt_id},
        )
        db.commit()
    except Exception:
        db.rollback()



# ─── Страницы (HTML) ────────────────────────────

@app.get("/")
def index():
    return FileResponse("frontend/index.html")


@app.get("/teacher_page")
def teacher_page():
    return FileResponse("frontend/teacher_page.html")


@app.get("/student_page")
def student_page():
    return FileResponse("frontend/student_page.html")


@app.get("/teacher.html")
def teacher():
    return FileResponse("frontend/teacher.html")


@app.get("/student.html")
def student():
    return FileResponse("frontend/student.html")


@app.get("/smart_notes.html")
def smart_notes_page():
    return FileResponse("frontend/smart_note.html")


@app.get("/test_page")
def test_page():
    return FileResponse("frontend/test_page.html")


@app.get("/debug_auth")
def debug_auth_page():
    return FileResponse("frontend/debug_auth.html")


# ─── АВТОРИЗАЦИЯ ЧЕРЕЗ MAX ──────────────────────

def get_or_create_user(db: Session, max_user: dict) -> User:
    name = display_name(max_user)
    user = db.query(User).filter(User.max_id == max_user["id"]).first()

    if user is None:
        try:
            user = User(max_id=max_user["id"], username=name)
            db.add(user)
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.query(User).filter(User.max_id == max_user["id"]).first()
    elif user.username != name:
        user.username = name
        db.commit()

    return user


def user_from_init_data(init_data: str | None, db: Session) -> User:
    try:
        data = validate_init_data(init_data or "", os.getenv("MAX_TOKEN", ""))
    except InitDataError as e:
        raise HTTPException(status_code=401, detail={"code": e.code, "message": str(e)})

    return get_or_create_user(db, data["user"])


def get_current_user(
    x_max_init_data: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    return user_from_init_data(x_max_init_data, db)


@app.post("/auth/max", response_model=UserResponse)
def auth_max(data: MaxAuthRequest, db: Session = Depends(get_db)):
    return user_from_init_data(data.init_data, db)


@app.get("/auth/me", response_model=UserResponse)
def auth_me(user: User = Depends(get_current_user)):
    return user


# ─── УМНЫЙ КОНСПЕКТ ─────────────────────────────

MAX_NOTES_INPUT_LENGTH = 15000


def extract_text_from_pdf(raw: bytes) -> str:
    doc = fitz.open(stream=raw, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


@app.post("/generate-notes")
def generate_notes(data: GenerateNotesRequest):
    if data.mode == "topic":
        topic = (data.topic or "").strip()
        if not topic:
            raise HTTPException(status_code=400, detail="Не указана тема конспекта")
        try:
            notes = generate_notes_by_topic(topic)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Ошибка генерации конспекта: {e}")

    elif data.mode == "text":
        content = (data.content or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="Не передан текст для конспекта")
        try:
            notes = generate_notes_by_text(content[:MAX_NOTES_INPUT_LENGTH])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Ошибка генерации конспекта: {e}")

    else:
        raise HTTPException(status_code=400, detail="Неизвестный режим генерации конспекта")

    return {"notes": notes}


@app.post("/generate-notes-from-file")
async def generate_notes_from_file(file: UploadFile = File(...)):
    raw = await file.read()
    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".pdf"):
            text = extract_text_from_pdf(raw)
        else:
            text = raw.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать файл: {e}")

    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=400,
            detail="Не удалось извлечь текст из файла — он пуст или повреждён",
        )

    try:
        notes = generate_notes_by_text(text[:MAX_NOTES_INPUT_LENGTH])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка генерации конспекта: {e}")

    return {"notes": notes}


# ─── ТЕСТЫ ──────────────────────────────────────

@app.post("/tests", response_model=TestResponse)
def create_test(test: TestCreate, db: Session = Depends(get_db)):
    new_test = models.Test(
        creator_id=test.creator_id,
        title=test.title,
        description=test.description,
        access_code=generate_code(),
    )
    db.add(new_test)
    db.commit()
    db.refresh(new_test)
    return new_test


@app.post("/tests/{test_id}/questions", response_model=QuestionResponse)
def create_question(test_id: int, question: QuestionCreate, db: Session = Depends(get_db)):
    new_question = models.Question(
        test_id=test_id,
        text=question.text,
        order_number=question.order_number,
    )
    db.add(new_question)
    db.commit()
    db.refresh(new_question)
    return new_question


@app.post("/questions/{question_id}/answers", response_model=AnswerOptionResponse)
def create_answer(question_id: int, answer: AnswerOptionCreate, db: Session = Depends(get_db)):
    new_answer = models.AnswerOption(
        question_id=question_id,
        text=answer.text,
        is_correct=answer.is_correct,
    )
    db.add(new_answer)
    db.commit()
    db.refresh(new_answer)
    return new_answer


@app.get("/tests/code/{code}", response_model=TestPublic)
def get_test_by_code(code: str, db: Session = Depends(get_db)):
    test = (
        db.query(models.Test)
        .options(joinedload(models.Test.questions).joinedload(models.Question.answers))
        .filter(models.Test.access_code == code)
        .first()
    )
    if not test:
        return {"error": "Test not found"}
    return test


@app.post("/tests/save")
def save_test(
    data: SaveTestRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total_sec = compute_time_limit_seconds(data.time_limit_minutes, data.time_limit_seconds)
    time_limit_min = (total_sec // 60) if total_sec else None

    # max_attempts: 1 по умолчанию; 0 / None = без лимита
    max_att = data.max_attempts
    if max_att is None:
        max_att = 1

    subject = (data.subject or "").strip() or None

    test = Test(
        title=data.title,
        description=data.description,
        subject=subject,
        creator_id=user.id,
        access_code=generate_code(),
        time_limit_minutes=time_limit_min,
        time_limit_seconds=total_sec,
        is_draft=bool(data.is_draft),
        max_attempts=max_att,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    for q in data.questions:
        question = Question(
            test_id=test.id,
            text=q.text,
            explanation=q.explanation,
        )
        db.add(question)
        db.commit()
        db.refresh(question)

        for answer in q.answers:
            option = AnswerOption(
                question_id=question.id,
                text=answer.text,
                is_correct=answer.is_correct,
            )
            db.add(option)

    db.commit()

    notify_result = None
    if data.notify and not test.is_draft:
        notify_result = notify_students_about_test(
            db, user.id, test,
            class_id=data.class_id,
            class_ids=getattr(data, "class_ids", None),
            request=request,
        )

    return {
        "message": "Черновик сохранён" if test.is_draft else "Тест создан",
        "test_id": test.id,
        "code": test.access_code,
        "time_limit_minutes": test.time_limit_minutes,
        "time_limit_seconds": test.time_limit_seconds,
        "is_draft": test.is_draft,
        "notify": notify_result,
    }


@app.post("/attempts/{attempt_id}/submit")
def submit_test(
    attempt_id: int,
    data: SubmitTestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt = (
        db.query(models.TestAttempt)
        .filter(models.TestAttempt.id == attempt_id)
        .first()
    )

    if not attempt:
        raise HTTPException(status_code=404, detail="Попытка не найдена")

    if attempt.student_id != user.id:
        raise HTTPException(status_code=403, detail="Это не ваша попытка")

    if attempt.score is not None:
        raise HTTPException(status_code=409, detail="Попытка уже завершена")

    # Собираем ответы пользователя: {question_id: answer_id}
    user_answers = {a.question_id: a.answer_id for a in data.answers}

    # Берём все вопросы теста
    questions = (
        db.query(Question)
        .filter(Question.test_id == attempt.test_id)
        .order_by(Question.order_number, Question.id)
        .all()
    )

    score = 0
    wrong_answers = []

    for q in questions:
        chosen_id = user_answers.get(q.id)
        if chosen_id is None:
            # вопрос без ответа — считаем неправильным
            correct = next((a for a in q.answers if a.is_correct), None)
            wrong_answers.append({
                "question_id": q.id,
                "question": q.text,
                "your_answer": None,
                "correct_answer": correct.text if correct else None,
                "explanation": q.explanation,
            })
            continue

        chosen = next((a for a in q.answers if a.id == chosen_id), None)
        if chosen is None:
            raise HTTPException(400, "Неизвестный вариант ответа")

        # Сохраняем ответ студента
        db.add(models.StudentAnswer(
            attempt_id=attempt_id,
            question_id=q.id,
            answer_id=chosen_id,
        ))

        if chosen.is_correct:
            score += 1
        else:
            correct = next((a for a in q.answers if a.is_correct), None)
            wrong_answers.append({
                "question_id": q.id,
                "question": q.text,
                "your_answer": chosen.text,
                "correct_answer": correct.text if correct else None,
                "explanation": q.explanation,
            })

    attempt.score = score
    db.commit()
    write_cheat_stats(db, attempt_id, data.leave_count or 0, data.hidden_seconds or 0)

    return {
        "attempt_id": attempt_id,
        "score": score,
        "total": len(questions),
        "wrong_answers": wrong_answers,
        "leave_count": data.leave_count or 0,
        "hidden_seconds": data.hidden_seconds or 0,
    }

@app.post("/tests/{code}/start")
def start_test(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    test = db.query(Test).filter(Test.access_code == code).first()

    if not test:
        return {"error": "Тест не найден"}
    if getattr(test, "is_draft", False):
        raise HTTPException(404, "Тест ещё не опубликован")

    # По умолчанию одна попытка (max_attempts=1). 0 или None = без лимита.
    max_att = getattr(test, "max_attempts", 1)
    if max_att is None:
        max_att = 1
    if max_att > 0:
        done_count = (
            db.query(models.TestAttempt)
            .filter(
                models.TestAttempt.test_id == test.id,
                models.TestAttempt.student_id == user.id,
                models.TestAttempt.score.isnot(None),
            )
            .count()
        )
        if done_count >= max_att:
            raise HTTPException(
                403,
                f"Вы уже проходили этот тест (лимит: {max_att} "
                f"{'попытка' if max_att == 1 else 'попытки' if max_att < 5 else 'попыток'}).",
            )

    attempt = models.TestAttempt(
        test_id=test.id,
        student_id=user.id,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "test_id": test.id,
        "student_id": user.id,
        "time_limit_minutes": test.time_limit_minutes,
        "time_limit_seconds": resolve_time_limit_seconds(test),
    }


@app.get("/attempts/{attempt_id}/result")
def get_result(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt = (
        db.query(models.TestAttempt)
        .filter(models.TestAttempt.id == attempt_id)
        .first()
    )

    if not attempt:
        raise HTTPException(status_code=404, detail="Попытка не найдена")

    creator_id = (
        db.query(Test.creator_id).filter(Test.id == attempt.test_id).scalar()
    )
    if user.id not in (attempt.student_id, creator_id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому результату")

    total = db.query(Question).filter(Question.test_id == attempt.test_id).count()

    percent = 0
    if total > 0:
        percent = attempt.score / total * 100

    return {
        "test_id": attempt.test_id,
        "score": attempt.score,
        "total": total,
        "percent": percent,
    }


@app.post("/users/auth", response_model=UserResponse)
def auth_user(data: UserAuth, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.max_id == data.max_id).first()

    if not user:
        user = User(max_id=data.max_id, username=data.username)
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


# ─── ГЕНЕРАЦИЯ ТЕСТА (GigaChat) ──────────────────

@app.post("/generate-test", response_model=GeneratedTestResponse)
def generate_test(data: GenerateTestRequest):
    if data.mode == "topic":
        result = generate_quiz_by_topic(data.topic, data.question_count)
    elif data.mode == "text":
        result = generate_quiz_by_text(data.content, data.question_count)
    elif data.mode == "custom":
        result = create_custom_quiz(data.questions)
    else:
        return {"error": "Неизвестный режим"}

    return result



@app.get("/api/class/classes", response_model=list[ClassOut])
def list_classes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # MVP: удаляем пустые классы (0 учеников), оставляем один
    rows = (
        db.query(
            Class,
            func.count(ClassMember.id).label("student_count"),
        )
        .outerjoin(ClassMember, ClassMember.class_id == Class.id)
        .filter(Class.teacher_id == user.id)
        .group_by(Class.id)
        .order_by(Class.created_at.desc())
        .all()
    )
    cleaned = []
    for c, cnt in rows:
        if cnt == 0:
            db.delete(c)
        else:
            cleaned.append((c, cnt))
    if any(cnt == 0 for _, cnt in rows):
        db.commit()
    # Если осталось несколько непустых — для MVP отдаём только самый новый
    if len(cleaned) > 1:
        cleaned = cleaned[:1]
    return [
        ClassOut(id=c.id, name=c.name, student_count=cnt)
        for c, cnt in cleaned
    ]


@app.post("/api/class/classes", response_model=ClassOut)
def create_class(
    data: CreateClassIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = data.name.strip()
    if not name:
        raise HTTPException(400, "Имя класса не может быть пустым")

    # MVP: один класс на учителя
    existing = db.query(Class).filter(Class.teacher_id == user.id).all()
    for c in existing:
        cnt = db.query(ClassMember).filter(ClassMember.class_id == c.id).count()
        if cnt == 0:
            db.delete(c)
        else:
            raise HTTPException(400, "У вас уже есть класс. Для MVP достаточно одного.")
    db.commit()

    cls = Class(name=name, teacher_id=user.id)
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return ClassOut(id=cls.id, name=cls.name, student_count=0)


@app.get("/api/class/classes/{class_id}/students", response_model=list[StudentOut])
def list_class_students(
    class_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cls = (
        db.query(Class)
        .filter(Class.id == class_id, Class.teacher_id == user.id)
        .first()
    )
    if not cls:
        raise HTTPException(404, "Класс не найден")

    return [m.student for m in cls.members]


@app.get("/api/class/students", response_model=list[StudentOut])
def list_all_students(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(User)
        .join(ClassMember, ClassMember.student_id == User.id)
        .join(Class, Class.id == ClassMember.class_id)
        .filter(Class.teacher_id == user.id)
        .distinct()
        .all()
    )


@app.post("/api/class/students", response_model=StudentOut)
def add_student(
    data: AddStudentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cls = (
        db.query(Class)
        .filter(Class.id == data.class_id, Class.teacher_id == user.id)
        .first()
    )
    if not cls:
        raise HTTPException(404, "Класс не найден")

    student = db.query(User).filter(User.max_id == data.max_id).first()
    if not student:
        raise HTTPException(
            404,
            "Пользователь с таким MAX ID не найден. "
            "Пусть он сначала напишет боту команду /myid.",
        )

    # Демо: можно добавить себя учеником в свой класс
    exists = (
        db.query(ClassMember)
        .filter(
            ClassMember.class_id == cls.id,
            ClassMember.student_id == student.id,
        )
        .first()
    )
    if exists:
        raise HTTPException(400, "Ученик уже в этом классе")

    db.add(ClassMember(class_id=cls.id, student_id=student.id))
    db.commit()
    return student


@app.delete("/api/class/classes/{class_id}/students/{student_id}")
def remove_student(
    class_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cls = (
        db.query(Class)
        .filter(Class.id == class_id, Class.teacher_id == user.id)
        .first()
    )
    if not cls:
        raise HTTPException(404, "Класс не найден")

    link = (
        db.query(ClassMember)
        .filter(
            ClassMember.class_id == class_id,
            ClassMember.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(404, "Ученик не в этом классе")

    db.delete(link)
    db.commit()
    return {"ok": True}


@app.get("/class_page")
def class_page():
    return FileResponse("frontend/class_page.html")

@app.get("/api/student/history", response_model=list[AttemptHistoryItem])
def student_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(TestAttempt, Test)
        .join(Test, Test.id == TestAttempt.test_id)
        .filter(TestAttempt.student_id == user.id)
        .order_by(TestAttempt.id.desc())
        .all()
    )

    if not rows:
        return []

    test_ids = list({t.id for _, t in rows})
    totals = dict(
        db.query(Question.test_id, func.count(Question.id))
        .filter(Question.test_id.in_(test_ids))
        .group_by(Question.test_id)
        .all()
    )

    result = []
    for attempt, test in rows:
        total = totals.get(test.id, 0)
        percent = None
        if attempt.score is not None and total > 0:
            percent = attempt.score / total * 100

        leave_count, hidden_seconds = read_cheat_stats(db, attempt.id)

        result.append(AttemptHistoryItem(
            attempt_id=attempt.id,
            test_id=test.id,
            test_title=test.title or "Без названия",
            score=attempt.score,
            total=total,
            percent=percent,
            leave_count=leave_count,
            hidden_seconds=hidden_seconds,
        ))
    return result


@app.get("/api/student/attempts/{attempt_id}/detail", response_model=StudentAttemptDetail)
def student_attempt_detail(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt = (
        db.query(models.TestAttempt)
        .options(load_only(
            models.TestAttempt.id,
            models.TestAttempt.test_id,
            models.TestAttempt.student_id,
            models.TestAttempt.score,
        ))
        .filter(models.TestAttempt.id == attempt_id)
        .first()
    )
    if not attempt:
        raise HTTPException(404, "Попытка не найдена")
    if attempt.student_id != user.id:
        raise HTTPException(403, "Нет доступа")

    test = db.query(Test).filter(Test.id == attempt.test_id).first()
    questions = (
        db.query(Question)
        .options(joinedload(Question.answers))
        .filter(Question.test_id == attempt.test_id)
        .order_by(Question.order_number, Question.id)
        .all()
    )
    total = len(questions)
    percent = None
    if attempt.score is not None and total > 0:
        percent = attempt.score / total * 100

    sa_rows = (
        db.query(StudentAnswer)
        .filter(StudentAnswer.attempt_id == attempt_id)
        .all()
    )
    chosen_map = {r.question_id: r.answer_id for r in sa_rows}

    wrong_answers = []
    for q in questions:
        chosen_id = chosen_map.get(q.id)
        correct = next((a for a in q.answers if a.is_correct), None)
        chosen = next((a for a in q.answers if a.id == chosen_id), None) if chosen_id else None
        is_ok = chosen is not None and chosen.is_correct
        if not is_ok:
            wrong_answers.append({
                "question_id": q.id,
                "question": q.text,
                "your_answer": chosen.text if chosen else None,
                "correct_answer": correct.text if correct else None,
                "explanation": q.explanation,
            })

    hardest_text = None
    all_attempts = (
        db.query(models.TestAttempt)
        .filter(
            models.TestAttempt.test_id == attempt.test_id,
            models.TestAttempt.score.isnot(None),
        )
        .all()
    )
    if all_attempts and questions:
        q_stats = {q.id: {"wrong": 0, "total": 0, "text": q.text} for q in questions}
        for att in all_attempts:
            rows = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == att.id).all()
            cmap = {r.question_id: r.answer_id for r in rows}
            for q in questions:
                q_stats[q.id]["total"] += 1
                cid = cmap.get(q.id)
                chosen = next((a for a in q.answers if a.id == cid), None) if cid else None
                if not (chosen and chosen.is_correct):
                    q_stats[q.id]["wrong"] += 1
        scored = [(sid, st) for sid, st in q_stats.items() if st["total"] > 0]
        if scored:
            ratios = [(sid, st["wrong"] / st["total"], st) for sid, st in scored]
            max_ratio = max(r for _, r, _ in ratios)
            worst = [st for _, r, st in ratios if r == max_ratio]
            # Только один однозначно самый сложный и не все ответили верно
            if len(worst) == 1 and max_ratio > 0:
                hardest_text = worst[0]["text"]

    return StudentAttemptDetail(
        attempt_id=attempt.id,
        test_id=attempt.test_id,
        test_title=test.title if test else "Без названия",
        score=attempt.score,
        total=total,
        percent=percent,
        leave_count=read_cheat_stats(db, attempt.id)[0],
        hidden_seconds=read_cheat_stats(db, attempt.id)[1],
        wrong_answers=wrong_answers,
        hardest_question_text=hardest_text,
    )


@app.get("/api/teacher/tests", response_model=list[JournalTestItem])
def teacher_tests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tests = (
        db.query(Test)
        .filter(Test.creator_id == user.id)
        .order_by(Test.id.desc())
        .all()
    )
    if not tests:
        return []

    test_ids = [t.id for t in tests]
    q_counts = dict(
        db.query(Question.test_id, func.count(Question.id))
        .filter(Question.test_id.in_(test_ids))
        .group_by(Question.test_id)
        .all()
    )
    a_counts = dict(
        db.query(TestAttempt.test_id, func.count(TestAttempt.id))
        .filter(
            TestAttempt.test_id.in_(test_ids),
            TestAttempt.score.isnot(None),
        )
        .group_by(TestAttempt.test_id)
        .all()
    )

    def _fmt_dt(dt):
        if not dt:
            return None
        try:
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return str(dt)[:10]

    return [
        JournalTestItem(
            test_id=t.id,
            title=t.title or "Без названия",
            access_code=t.access_code or "",
            question_count=q_counts.get(t.id, 0),
            attempt_count=a_counts.get(t.id, 0),
            created_at=_fmt_dt(getattr(t, "created_at", None)),
        )
        for t in tests
    ]


@app.get("/api/teacher/tests/{test_id}/analytics", response_model=TestAnalytics)
def teacher_test_analytics(
    test_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    test = db.query(Test).filter(Test.id == test_id, Test.creator_id == user.id).first()
    if not test:
        raise HTTPException(404, "Тест не найден")

    questions = (
        db.query(Question)
        .options(joinedload(Question.answers))
        .filter(Question.test_id == test_id)
        .order_by(Question.order_number, Question.id)
        .all()
    )
    total_q = len(questions)

    # Только базовые колонки — чтобы не падать, если leave_count/hidden_seconds ещё нет в БД
    attempts = (
        db.query(models.TestAttempt)
        .options(load_only(
            models.TestAttempt.id,
            models.TestAttempt.test_id,
            models.TestAttempt.student_id,
            models.TestAttempt.score,
        ))
        .filter(
            models.TestAttempt.test_id == test_id,
            models.TestAttempt.score.isnot(None),
        )
        .all()
    )

    q_stats = {
        q.id: {"correct": 0, "wrong": 0, "text": q.text}
        for q in questions
    }

    students_out = []
    score_sum = 0.0
    for att in attempts:
        student = db.query(User).filter(User.id == att.student_id).first()
        percent = (att.score / total_q * 100) if total_q and att.score is not None else None
        if percent is not None:
            score_sum += percent

        leave_count, hidden_seconds = read_cheat_stats(db, att.id)

        students_out.append(JournalStudentScore(
            student_id=att.student_id,
            username=display_student_name(student),
            score=att.score,
            total=total_q,
            percent=percent,
            leave_count=leave_count,
            hidden_seconds=hidden_seconds,
            attempt_id=att.id,
        ))

        rows = (
            db.query(StudentAnswer)
            .filter(StudentAnswer.attempt_id == att.id)
            .all()
        )
        cmap = {r.question_id: r.answer_id for r in rows}
        for q in questions:
            cid = cmap.get(q.id)
            chosen = next((a for a in q.answers if a.id == cid), None) if cid else None
            if chosen and chosen.is_correct:
                q_stats[q.id]["correct"] += 1
            else:
                q_stats[q.id]["wrong"] += 1

    question_stats = []
    for qid, s in q_stats.items():
        tot = s["correct"] + s["wrong"]
        pct = (s["correct"] / tot * 100) if tot else 0.0
        question_stats.append(QuestionStat(
            question_id=qid,
            text=s["text"],
            correct_count=s["correct"],
            wrong_count=s["wrong"],
            total_answers=tot,
            correct_percent=round(pct, 1),
        ))

    hardest = None
    with_answers = [q for q in question_stats if q.total_answers > 0]
    if with_answers:
        min_pct = min(q.correct_percent for q in with_answers)
        worst = [q for q in with_answers if q.correct_percent == min_pct]
        # Показываем только если один однозначно самый сложный и не 100%
        if len(worst) == 1 and min_pct < 100.0:
            hardest = worst[0]

    avg_percent = round(score_sum / len(attempts), 1) if attempts else None
    students_out.sort(key=lambda s: (s.username or "").lower())

    return TestAnalytics(
        test_id=test.id,
        title=test.title or "Без названия",
        question_count=total_q,
        attempt_count=len(attempts),
        avg_percent=avg_percent,
        hardest_question=hardest,
        questions=question_stats,
        students=students_out,
    )



@app.get("/api/teacher/gradebook", response_model=GradebookResponse)
def teacher_gradebook(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Все ученики учителя (из классов) + оценки по всем тестам."""
    tests = (
        db.query(Test)
        .options(load_only(
            Test.id,
            Test.title,
            Test.access_code,
            Test.creator_id,
        ))
        .filter(Test.creator_id == user.id)
        .order_by(Test.id.desc())
        .all()
    )
    test_ids = [t.id for t in tests]
    q_counts = {}
    a_counts = {}
    if test_ids:
        q_counts = dict(
            db.query(Question.test_id, func.count(Question.id))
            .filter(Question.test_id.in_(test_ids))
            .group_by(Question.test_id)
            .all()
        )
        a_counts = dict(
            db.query(TestAttempt.test_id, func.count(TestAttempt.id))
            .filter(TestAttempt.test_id.in_(test_ids), TestAttempt.score.isnot(None))
            .group_by(TestAttempt.test_id)
            .all()
        )

    # даты создания (день.месяц) — отдельным запросом, чтобы не падать без колонки
    created_map = {}
    if test_ids:
        try:
            from sqlalchemy import text as sa_text
            ids_sql = ",".join(str(int(i)) for i in test_ids)
            rows = db.execute(
                sa_text(f"SELECT id, created_at FROM tests WHERE id IN ({ids_sql})")
            ).fetchall()
            for rid, cdt in rows:
                if cdt is not None:
                    try:
                        created_map[rid] = cdt.strftime("%d.%m")
                    except Exception:
                        created_map[rid] = str(cdt)[8:10] + "." + str(cdt)[5:7] if len(str(cdt)) >= 10 else None
        except Exception:
            db.rollback()

    test_items = [
        JournalTestItem(
            test_id=t.id,
            title=t.title or "Без названия",
            access_code=t.access_code or "",
            question_count=q_counts.get(t.id, 0),
            attempt_count=a_counts.get(t.id, 0),
            created_at=created_map.get(t.id),
        )
        for t in tests
    ]

    # ученики из классов учителя
    students = (
        db.query(User)
        .join(ClassMember, ClassMember.student_id == User.id)
        .join(Class, Class.id == ClassMember.class_id)
        .filter(Class.teacher_id == user.id)
        .distinct()
        .order_by(User.username)
        .all()
    )

    # лучшая (последняя завершённая) попытка ученика по каждому тесту
    students_out = []
    for st in students:
        scores = []
        for t in tests:
            att = (
                db.query(TestAttempt)
                .options(load_only(
                    TestAttempt.id,
                    TestAttempt.test_id,
                    TestAttempt.student_id,
                    TestAttempt.score,
                ))
                .filter(
                    TestAttempt.test_id == t.id,
                    TestAttempt.student_id == st.id,
                    TestAttempt.score.isnot(None),
                )
                .order_by(TestAttempt.id.desc())
                .first()
            )
            total = q_counts.get(t.id, 0)
            percent = None
            if att and total > 0 and att.score is not None:
                percent = att.score / total * 100
            scores.append(GradebookScore(
                test_id=t.id,
                score=att.score if att else None,
                total=total,
                percent=percent,
                attempt_id=att.id if att else None,
            ))
        students_out.append(GradebookStudent(
            student_id=st.id,
            username=display_student_name(st),
            max_id=st.max_id,
            scores=scores,
        ))

    return GradebookResponse(tests=test_items, students=students_out)




@app.get("/api/teacher/drafts", response_model=list[DraftTestItem])
def list_drafts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tests = (
        db.query(Test)
        .filter(Test.creator_id == user.id, Test.is_draft == True)
        .order_by(Test.id.desc())
        .all()
    )
    out = []
    for te in tests:
        created = None
        try:
            if getattr(te, "created_at", None):
                created = te.created_at.strftime("%d.%m.%Y")
        except Exception:
            pass
        out.append(DraftTestItem(
            test_id=te.id,
            title=te.title or "Без названия",
            description=te.description,
            subject=getattr(te, "subject", None),
            access_code=te.access_code or "",
            time_limit_seconds=resolve_time_limit_seconds(te),
            created_at=created,
        ))
    return out


@app.post("/api/teacher/tests/{test_id}/publish")
def publish_draft(
    test_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    test = db.query(Test).filter(Test.id == test_id, Test.creator_id == user.id).first()
    if not test:
        raise HTTPException(404, "Тест не найден")
    test.is_draft = False
    db.commit()
    return {
        "message": "Тест опубликован",
        "test_id": test.id,
        "code": test.access_code,
        "is_draft": False,
    }



@app.post("/api/teacher/tests/{test_id}/notify")
def notify_test(
    test_id: int,
    request: Request,
    data: NotifyTestRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    test = db.query(Test).filter(Test.id == test_id, Test.creator_id == user.id).first()
    if not test:
        raise HTTPException(404, "Тест не найден")
    if test.is_draft:
        test.is_draft = False
        db.commit()
    class_id = data.class_id if data else None
    class_ids = data.class_ids if data else None
    result = notify_students_about_test(
        db, user.id, test,
        class_id=class_id,
        class_ids=class_ids,
        request=request,
    )
    return {"message": "Уведомления отправлены", **result}


@app.get("/api/tests/entry/{code}", response_model=TestEntryInfo)
def test_entry_info(code: str, db: Session = Depends(get_db)):
    test = db.query(Test).filter(Test.access_code == code).first()
    if not test:
        raise HTTPException(404, "Тест не найден")
    if getattr(test, "is_draft", False):
        raise HTTPException(404, "Тест ещё не опубликован")
    qcount = db.query(Question).filter(Question.test_id == test.id).count()
    return TestEntryInfo(
        id=test.id,
        title=test.title or "Без названия",
        description=test.description,
        subject=getattr(test, "subject", None),
        access_code=test.access_code,
        time_limit_seconds=resolve_time_limit_seconds(test),
        question_count=qcount,
    )


@app.get("/api/public-config")
def public_config():
    """Публичные настройки для фронта (username бота для QR/диплинков)."""
    return {
        "bot_username": bot_username(),
        "max_deep_link_base": f"https://max.ru/{bot_username()}" if bot_username() else None,
    }



@app.get("/api/teacher/tests/{test_id}/manage")
def teacher_test_manage(
    test_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Карточка теста для учителя: код, QR-данные, статус, время."""
    test = db.query(Test).filter(Test.id == test_id, Test.creator_id == user.id).first()
    if not test:
        raise HTTPException(404, "Тест не найден")
    qcount = db.query(Question).filter(Question.test_id == test.id).count()
    attempts = (
        db.query(TestAttempt)
        .filter(TestAttempt.test_id == test.id, TestAttempt.score.isnot(None))
        .count()
    )
    created = None
    try:
        if getattr(test, "created_at", None):
            created = test.created_at.strftime("%d.%m.%Y %H:%M")
    except Exception:
        pass
    return {
        "test_id": test.id,
        "title": test.title or "Без названия",
        "description": test.description,
        "subject": getattr(test, "subject", None),
        "access_code": test.access_code or "",
        "is_draft": bool(getattr(test, "is_draft", False)),
        "time_limit_seconds": resolve_time_limit_seconds(test),
        "question_count": qcount,
        "attempt_count": attempts,
        "created_at": created,
        "deep_link_payload": f"test_{test.access_code}" if test.access_code else None,
    }


@app.get("/api/teacher/my-tests")
def teacher_my_tests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Все тесты учителя: черновики и опубликованные."""
    tests = (
        db.query(Test)
        .filter(Test.creator_id == user.id)
        .order_by(Test.id.desc())
        .all()
    )
    out = []
    for te in tests:
        created = None
        try:
            if getattr(te, "created_at", None):
                created = te.created_at.strftime("%d.%m.%Y")
        except Exception:
            pass
        out.append({
            "test_id": te.id,
            "title": te.title or "Без названия",
            "description": te.description,
            "subject": getattr(te, "subject", None),
            "access_code": te.access_code or "",
            "is_draft": bool(getattr(te, "is_draft", False)),
            "time_limit_seconds": resolve_time_limit_seconds(te),
            "created_at": created,
        })
    return out


@app.get("/drafts_page")
def drafts_page():
    return FileResponse("frontend/drafts_page.html")


@app.get("/my_tests")
def my_tests_page():
    return FileResponse("frontend/drafts_page.html")


@app.get("/teacher_test")
def teacher_test_page():
    return FileResponse("frontend/teacher_test.html")



@app.get("/test_entry")
def test_entry_page():
    return FileResponse("frontend/test_entry.html")

@app.get("/history_page")
def history_page():
    return FileResponse("frontend/history_page.html")


@app.get("/journal_page")
def journal_page():
    return FileResponse("frontend/journal_page.html")


@app.get("/analytics_page")
def analytics_page():
    return FileResponse("frontend/analytics_page.html")


@app.get("/api/teacher/dashboard")
def teacher_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Сводная аналитика для учителя:
    - статистика по тестам (средний %, число сдач, худшие тесты)
    - рейтинг учеников
    """
    tests = (
        db.query(Test)
        .filter(Test.creator_id == user.id, Test.is_draft.is_(False))
        .order_by(Test.id.desc())
        .all()
    )
    test_ids = [t.id for t in tests]

    # Вопросы по тестам
    q_counts = {}
    if test_ids:
        q_counts = dict(
            db.query(Question.test_id, func.count(Question.id))
            .filter(Question.test_id.in_(test_ids))
            .group_by(Question.test_id)
            .all()
        )

    # Все завершённые попытки учителя
    attempts = []
    if test_ids:
        attempts = (
            db.query(models.TestAttempt)
            .options(load_only(
                models.TestAttempt.id,
                models.TestAttempt.test_id,
                models.TestAttempt.student_id,
                models.TestAttempt.score,
            ))
            .filter(
                models.TestAttempt.test_id.in_(test_ids),
                models.TestAttempt.score.isnot(None),
            )
            .all()
        )

    # Группировка попыток по тесту и ученику
    by_test: dict[int, list] = {}
    by_student: dict[int, list] = {}
    for att in attempts:
        by_test.setdefault(att.test_id, []).append(att)
        by_student.setdefault(att.student_id, []).append(att)

    tests_out = []
    for t in tests:
        atts = by_test.get(t.id, [])
        total_q = q_counts.get(t.id, 0) or 0
        pcts = []
        for a in atts:
            if total_q and a.score is not None:
                pcts.append(a.score / total_q * 100)
        avg = round(sum(pcts) / len(pcts), 1) if pcts else None
        tests_out.append({
            "test_id": t.id,
            "title": t.title or "Без названия",
            "access_code": t.access_code or "",
            "question_count": total_q,
            "attempt_count": len(atts),
            "avg_percent": avg,
            "unique_students": len({a.student_id for a in atts}),
        })

    # Худшие тесты — с хотя бы одной сдачей, по возрастанию среднего %
    worst_tests = sorted(
        [x for x in tests_out if x["attempt_count"] > 0 and x["avg_percent"] is not None],
        key=lambda x: x["avg_percent"],
    )[:5]

    # Лучшие тесты
    best_tests = sorted(
        [x for x in tests_out if x["attempt_count"] > 0 and x["avg_percent"] is not None],
        key=lambda x: x["avg_percent"],
        reverse=True,
    )[:5]

    # Ученики из классов учителя
    student_ids = (
        db.query(ClassMember.student_id)
        .join(Class, Class.id == ClassMember.class_id)
        .filter(Class.teacher_id == user.id)
        .distinct()
        .all()
    )
    student_ids = [sid for (sid,) in student_ids]

    students_meta = {}
    if student_ids:
        for u in db.query(User).filter(User.id.in_(student_ids)).all():
            students_meta[u.id] = u

    ranking = []
    for sid, atts in by_student.items():
        # Только ученики из классов (или все, кто сдавал)
        pcts = []
        for a in atts:
            tq = q_counts.get(a.test_id, 0) or 0
            if tq and a.score is not None:
                pcts.append(a.score / tq * 100)
        if not pcts:
            continue
        u = students_meta.get(sid) or db.query(User).filter(User.id == sid).first()
        ranking.append({
            "student_id": sid,
            "username": display_student_name(u),
            "max_id": getattr(u, "max_id", None) if u else None,
            "attempts": len(pcts),
            "avg_percent": round(sum(pcts) / len(pcts), 1),
            "best_percent": round(max(pcts), 1),
            "worst_percent": round(min(pcts), 1),
        })

    ranking.sort(key=lambda x: (-x["avg_percent"], -x["attempts"], x["username"] or ""))

    all_pcts = []
    for x in tests_out:
        if x["avg_percent"] is not None and x["attempt_count"]:
            # взвешиваем по числу сдач
            all_pcts.extend([x["avg_percent"]] * x["attempt_count"])
    overall_avg = round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else None

    return {
        "summary": {
            "tests_count": len(tests),
            "tests_with_attempts": sum(1 for x in tests_out if x["attempt_count"] > 0),
            "total_attempts": len(attempts),
            "students_count": len(student_ids),
            "students_who_attempted": len(by_student),
            "overall_avg_percent": overall_avg,
        },
        "worst_tests": worst_tests,
        "best_tests": best_tests,
        "tests": tests_out,
        "student_ranking": ranking,
    }



# ─── Редактирование черновика ────────────────────

@app.get("/api/teacher/tests/{test_id}/edit")
def get_draft_for_edit(
    test_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Полные данные черновика для редактора (вопросы + ответы)."""
    test = (
        db.query(Test)
        .options(
            joinedload(Test.questions).joinedload(Question.answers)
        )
        .filter(Test.id == test_id, Test.creator_id == user.id)
        .first()
    )
    if not test:
        raise HTTPException(404, "Тест не найден")
    if not getattr(test, "is_draft", False):
        raise HTTPException(400, "Редактировать можно только черновик")

    questions = []
    for q in sorted(test.questions or [], key=lambda x: (x.order_number or 0, x.id or 0)):
        questions.append({
            "text": q.text,
            "explanation": q.explanation,
            "answers": [
                {"text": a.text, "is_correct": bool(a.is_correct)}
                for a in (q.answers or [])
            ],
        })

    total_sec = resolve_time_limit_seconds(test)
    return {
        "test_id": test.id,
        "title": test.title or "",
        "description": test.description,
        "subject": getattr(test, "subject", None),
        "time_limit_seconds": total_sec,
        "time_limit_minutes": (total_sec // 60) if total_sec else 0,
        "max_attempts": test.max_attempts,
        "is_draft": True,
        "access_code": test.access_code,
        "questions": questions,
    }


@app.put("/api/teacher/tests/{test_id}")
def update_draft(
    test_id: int,
    data: UpdateDraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Обновить черновик: метаданные + полная замена вопросов."""
    test = db.query(Test).filter(Test.id == test_id, Test.creator_id == user.id).first()
    if not test:
        raise HTTPException(404, "Тест не найден")
    if not getattr(test, "is_draft", False):
        raise HTTPException(400, "Редактировать можно только черновик")

    total_sec = compute_time_limit_seconds(data.time_limit_minutes, data.time_limit_seconds)
    time_limit_min = (total_sec // 60) if total_sec else None
    max_att = data.max_attempts if data.max_attempts is not None else 1

    test.title = data.title
    test.description = data.description
    test.subject = (data.subject or "").strip() or None
    test.time_limit_minutes = time_limit_min
    test.time_limit_seconds = total_sec
    test.max_attempts = max_att

    # Удаляем старые вопросы и ответы
    old_qs = db.query(Question).filter(Question.test_id == test.id).all()
    for q in old_qs:
        db.query(AnswerOption).filter(AnswerOption.question_id == q.id).delete()
        db.delete(q)
    db.flush()

    for i, q in enumerate(data.questions or []):
        question = Question(
            test_id=test.id,
            text=q.text,
            explanation=q.explanation,
            order_number=i + 1,
        )
        db.add(question)
        db.flush()
        for answer in q.answers:
            db.add(AnswerOption(
                question_id=question.id,
                text=answer.text,
                is_correct=answer.is_correct,
            ))

    db.commit()
    db.refresh(test)
    return {
        "message": "Черновик обновлён",
        "test_id": test.id,
        "code": test.access_code,
        "is_draft": True,
        "subject": test.subject,
    }


# ─── Запланированные тесты (анонсы) ───────────────

def _parse_date(s: str) -> datetime:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise HTTPException(400, "Неверный формат даты. Используйте ГГГГ-ММ-ДД")


def _fmt_date(dt) -> str:
    if not dt:
        return ""
    try:
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return str(dt)


def _cleanup_past_scheduled(db: Session, teacher_id: int | None = None):
    """Удаляет анонсы, дата которых уже прошла (на следующий день после теста)."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    q = db.query(ScheduledTest).filter(ScheduledTest.scheduled_date < today_start)
    if teacher_id is not None:
        q = q.filter(ScheduledTest.teacher_id == teacher_id)
    deleted = q.delete(synchronize_session=False)
    if deleted:
        db.commit()
    return deleted


def _send_day_before_reminders(db: Session):
    """Напоминания за день до теста — вызывается при открытии списка."""
    tomorrow = date.today() + timedelta(days=1)
    day_start = datetime.combine(tomorrow, datetime.min.time())
    day_end = datetime.combine(tomorrow, datetime.max.time())
    items = (
        db.query(ScheduledTest)
        .filter(
            ScheduledTest.scheduled_date >= day_start,
            ScheduledTest.scheduled_date <= day_end,
            ScheduledTest.notified_day_before == False,  # noqa: E712
        )
        .all()
    )
    for item in items:
        students = (
            db.query(User)
            .join(ClassMember, ClassMember.student_id == User.id)
            .filter(ClassMember.class_id == item.class_id)
            .all()
        )
        text = (
            f"Напоминание: завтра тест\n"
            f"Предмет: {item.subject}\n"
            f"Тема: {item.title}\n"
            f"Дата: {_fmt_date(item.scheduled_date)}"
        )
        if item.description:
            text += f"\n{item.description}"
        for st in students:
            send_max_message(st.max_id, text)
        item.notified_day_before = True
    if items:
        db.commit()
    return len(items)


def _notify_scheduled_created(db: Session, item: ScheduledTest):
    students = (
        db.query(User)
        .join(ClassMember, ClassMember.student_id == User.id)
        .filter(ClassMember.class_id == item.class_id)
        .all()
    )
    text = (
        f"Запланирован тест\n"
        f"Предмет: {item.subject}\n"
        f"Тема: {item.title}\n"
        f"Дата: {_fmt_date(item.scheduled_date)}"
    )
    if item.description:
        text += f"\n{item.description}"
    if item.materials_text:
        text += "\nЕсть материалы для подготовки — откройте «Запланированные» в приложении."
    sent, failed = 0, 0
    for st in students:
        ok, _ = send_max_message(st.max_id, text)
        if ok:
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed, "total": len(students)}


def _teacher_single_class(db: Session, user: User) -> Class:
    classes = db.query(Class).filter(Class.teacher_id == user.id).all()
    non_empty = []
    for c in classes:
        cnt = db.query(ClassMember).filter(ClassMember.class_id == c.id).count()
        if cnt == 0:
            db.delete(c)
        else:
            non_empty.append(c)
    db.commit()
    if not non_empty:
        # разрешаем создать анонс и без учеников, если класс есть
        any_cls = db.query(Class).filter(Class.teacher_id == user.id).first()
        if any_cls:
            return any_cls
        raise HTTPException(400, "Сначала создайте класс в разделе «Мой класс»")
    return non_empty[0]


@app.post("/api/scheduled", response_model=ScheduledTestOut)
def create_scheduled(
    data: ScheduledTestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    title = (data.title or "").strip()
    subject = (data.subject or "").strip()
    if not title:
        raise HTTPException(400, "Укажите тему")
    if not subject:
        raise HTTPException(400, "Укажите предмет")

    cls = None
    if data.class_id:
        cls = (
            db.query(Class)
            .filter(Class.id == data.class_id, Class.teacher_id == user.id)
            .first()
        )
        if not cls:
            raise HTTPException(404, "Класс не найден")
    else:
        cls = _teacher_single_class(db, user)

    sched_dt = _parse_date(data.scheduled_date)
    # нормализуем к началу дня
    sched_dt = datetime.combine(sched_dt.date(), datetime.min.time())

    item = ScheduledTest(
        teacher_id=user.id,
        class_id=cls.id,
        title=title,
        subject=subject,
        description=(data.description or "").strip() or None,
        scheduled_date=sched_dt,
        materials_text=(data.materials_text or "").strip() or None,
        notified_day_before=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    notify_result = _notify_scheduled_created(db, item)

    return ScheduledTestOut(
        id=item.id,
        title=item.title,
        subject=item.subject,
        description=item.description,
        scheduled_date=_fmt_date(item.scheduled_date),
        materials_text=item.materials_text,
        class_id=item.class_id,
        class_name=cls.name,
        created_at=_fmt_date(item.created_at) if item.created_at else None,
        notified_day_before=bool(item.notified_day_before),
    )


@app.get("/api/scheduled", response_model=list[ScheduledTestOut])
def list_scheduled_teacher(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _cleanup_past_scheduled(db, teacher_id=user.id)
    _send_day_before_reminders(db)

    items = (
        db.query(ScheduledTest)
        .filter(ScheduledTest.teacher_id == user.id)
        .order_by(ScheduledTest.scheduled_date.asc())
        .all()
    )
    out = []
    for item in items:
        cls = db.query(Class).filter(Class.id == item.class_id).first()
        out.append(ScheduledTestOut(
            id=item.id,
            title=item.title,
            subject=item.subject,
            description=item.description,
            scheduled_date=_fmt_date(item.scheduled_date),
            materials_text=item.materials_text,
            class_id=item.class_id,
            class_name=cls.name if cls else None,
            created_at=_fmt_date(item.created_at) if item.created_at else None,
            notified_day_before=bool(item.notified_day_before),
        ))
    return out


@app.delete("/api/scheduled/{item_id}")
def delete_scheduled(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = (
        db.query(ScheduledTest)
        .filter(ScheduledTest.id == item_id, ScheduledTest.teacher_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Запись не найдена")
    db.delete(item)
    db.commit()
    return {"message": "Удалено"}


@app.get("/api/student/scheduled", response_model=list[ScheduledTestOut])
def list_scheduled_student(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _cleanup_past_scheduled(db)
    _send_day_before_reminders(db)

    class_ids = [
        r[0]
        for r in db.query(ClassMember.class_id)
        .filter(ClassMember.student_id == user.id)
        .all()
    ]
    if not class_ids:
        return []

    items = (
        db.query(ScheduledTest)
        .filter(ScheduledTest.class_id.in_(class_ids))
        .order_by(ScheduledTest.scheduled_date.asc())
        .all()
    )
    out = []
    for item in items:
        cls = db.query(Class).filter(Class.id == item.class_id).first()
        out.append(ScheduledTestOut(
            id=item.id,
            title=item.title,
            subject=item.subject,
            description=item.description,
            scheduled_date=_fmt_date(item.scheduled_date),
            materials_text=item.materials_text,
            class_id=item.class_id,
            class_name=cls.name if cls else None,
            created_at=_fmt_date(item.created_at) if item.created_at else None,
            notified_day_before=bool(item.notified_day_before),
        ))
    return out


@app.get("/api/scheduled/{item_id}/materials")
def download_materials(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Текст материалов — ученик или учитель класса."""
    item = db.query(ScheduledTest).filter(ScheduledTest.id == item_id).first()
    if not item:
        raise HTTPException(404, "Запись не найдена")

    is_teacher = item.teacher_id == user.id
    is_student = (
        db.query(ClassMember)
        .filter(
            ClassMember.class_id == item.class_id,
            ClassMember.student_id == user.id,
        )
        .first()
        is not None
    )
    if not is_teacher and not is_student:
        raise HTTPException(403, "Нет доступа")

    if not item.materials_text:
        raise HTTPException(404, "Материалов нет")

    from fastapi.responses import Response
    from urllib.parse import quote
    # ASCII-only filename — кириллица в Content-Disposition даёт 500 у части прокси
    safe_name = f"materials_{item.id}.txt"
    utf8_name = quote(f"materials_{item.subject or 'prep'}_{item.id}.txt".replace(" ", "_"))
    body = (item.materials_text or "").encode("utf-8")
    return Response(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_name}"; '
                f"filename*=UTF-8''{utf8_name}"
            ),
            "Content-Length": str(len(body)),
        },
    )


@app.get("/scheduled_page")
def scheduled_page():
    return FileResponse("frontend/scheduled_page.html")


@app.get("/student_scheduled")
def student_scheduled_page():
    return FileResponse("frontend/student_scheduled.html")
