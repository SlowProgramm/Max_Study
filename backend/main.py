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
)
from backend.models import Class, ClassMember, TestAttempt
from sqlalchemy import func
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

app = FastAPI(title="MAX Study")

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
) -> bool:
    """
    Отправка сообщения ученику через MAX Bot API.
    Токен тот же, что у бота: MAX_TOKEN (как в max_bot/settings и max_auth).
    """
    import httpx
    token = os.getenv("MAX_TOKEN", "")
    if not token:
        print("MAX notify: MAX_TOKEN не задан")
        return False
    payload = {"text": text}
    if button_url:
        # Обычная HTTPS-ссылка (тот же origin, что у мини-приложения / QR)
        payload["attachments"] = [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [[{
                    "type": "link",
                    "text": button_text,
                    "url": button_url,
                }]]
            }
        }]
    try:
        r = httpx.post(
            f"https://platform-api2.max.ru/messages?user_id={int(user_max_id)}",
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if r.status_code != 200:
            print("MAX notify status:", r.status_code, r.text[:300])
        return r.status_code == 200
    except Exception as e:
        print("MAX notify error:", e)
        return False



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
        time_line = f"\n⏱ Время: {mm} мин {ss} сек" if mm else f"\n⏱ Время: {ss} сек"

    text = (
        f"📚 Новый тест: {test.title or 'Без названия'}"
        f"{time_line}"
        f"\n🔑 Код: {code}"
    )
    if link:
        text += f"\n🔗 {link}"

    sent, failed = 0, 0
    for st in students:
        ok = send_max_message(st.max_id, text, button_url=link)
        if ok:
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed, "total": len(students), "link": link}

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

    test = Test(
        title=data.title,
        description=data.description,
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
    return [
        ClassOut(id=c.id, name=c.name, student_count=cnt)
        for c, cnt in rows
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

    if student.id == user.id:
        raise HTTPException(400, "Нельзя добавить самого себя")

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
        hardest = max(
            q_stats.values(),
            key=lambda s: (s["wrong"] / s["total"] if s["total"] else 0),
        )
        hardest_text = hardest["text"]

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
    if question_stats:
        hardest = min(question_stats, key=lambda x: x.correct_percent)

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
