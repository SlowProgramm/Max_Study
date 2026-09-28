from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend import models
import random

import string
from backend.models import (StudentAnswer, Test, Question, AnswerOption, User)
from fastapi.responses import FileResponse
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from sqlalchemy.exc import IntegrityError
import fitz  # pymupdf — для извлечения текста из PDF
from backend.gigachat_services import generate_notes_by_topic, generate_notes_by_text
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

    StartTestRequest
)


from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import joinedload

from pydantic import BaseModel


app = FastAPI(
    title="MAX Study"
)



app.mount(
    "/static",
    StaticFiles(directory="frontend"),
    name="static"
)

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



app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)





Base.metadata.create_all(
    bind=engine
)






def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()






def generate_code():

    return "".join(

        random.choices(

            string.ascii_uppercase + string.digits,

            k=6

        )

    )

@app.get("/")
def index():
    return FileResponse("frontend/index.html")


# =========================
# АВТОРИЗАЦИЯ ЧЕРЕЗ MAX
# =========================
# Личность берём ТОЛЬКО из проверенной подписи initData (токен бота = MAX_TOKEN),
# а не из того, что прислал браузер. Фронтенд шлёт initData в заголовке
# X-Max-Init-Data (или в теле для /auth/max).

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
            # Два параллельных первых запроса — второй споткнулся о unique(max_id).
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
        raise HTTPException(
            status_code=401,
            detail={"code": e.code, "message": str(e)}
        )

    return get_or_create_user(db, data["user"])


def get_current_user(
    x_max_init_data: str | None = Header(default=None),
    db: Session = Depends(get_db)
) -> User:
    return user_from_init_data(x_max_init_data, db)


class MaxAuthRequest(BaseModel):
    init_data: str


@app.post("/auth/max", response_model=UserResponse)
def auth_max(data: MaxAuthRequest, db: Session = Depends(get_db)):
    return user_from_init_data(data.init_data, db)


@app.get("/auth/me", response_model=UserResponse)
def auth_me(user: User = Depends(get_current_user)):
    return user


@app.get("/debug_auth")
def debug_auth_page():
    return FileResponse("frontend/debug_auth.html")


# =========================
# УМНЫЙ КОНСПЕКТ
# =========================

MAX_NOTES_INPUT_LENGTH = 15000  # ограничение длины текста, отправляемого в GigaChat


class GenerateNotesRequest(BaseModel):
    mode: str            # "topic" или "text"
    topic: str | None = None
    content: str | None = None


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
        raise HTTPException(status_code=400, detail="Не удалось извлечь текст из файла — он пуст или повреждён")

    try:
        notes = generate_notes_by_text(text[:MAX_NOTES_INPUT_LENGTH])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка генерации конспекта: {e}")

    return {"notes": notes}


# Создать тест
@app.post(
    "/tests",
    response_model=TestResponse
)
def create_test(
    test: TestCreate,
    db: Session = Depends(get_db)
):

    new_test = models.Test(

        creator_id=test.creator_id,

        title=test.title,

        description=test.description,

        access_code=generate_code()

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
        order_number=question.order_number
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
        is_correct=answer.is_correct
    )

    db.add(new_answer)
    db.commit()
    db.refresh(new_answer)

    return new_answer


@app.get("/tests/code/{code}", response_model=TestPublic)
def get_test_by_code(code: str, db: Session = Depends(get_db)):

    test = (
        db.query(models.Test)
        .options(
            joinedload(models.Test.questions)
            .joinedload(models.Question.answers)
        )
        .filter(
            models.Test.access_code == code
        )
        .first()
    )

    if not test:
        return {
            "error": "Test not found"
        }

    return test
#sa


@app.post("/tests/save")
def save_test(data: SaveTestRequest, db: Session = Depends(get_db)):

    test = Test(
        title=data.title,
        creator_id=data.creator_id,
        access_code=generate_code()
    )

    db.add(test)
    db.commit()
    db.refresh(test)

    for q in data.questions:

        question = Question(
            test_id=test.id,
            text=q.text,
            explanation=q.explanation
        )

        db.add(question)
        db.commit()
        db.refresh(question)

        for answer in q.answers:

            option = AnswerOption(
                question_id=question.id,
                text=answer.text,
                is_correct=answer.is_correct
            )

            db.add(option)

    db.commit()

    return {
        "message": "Тест создан",
        "test_id": test.id,
        "code": test.access_code
    }


@app.post("/attempts/{attempt_id}/submit")
def submit_test(
    attempt_id: int,
    data: SubmitTestRequest,
    db: Session = Depends(get_db)
):

    attempt = db.query(
        models.TestAttempt
    ).filter(
        models.TestAttempt.id == attempt_id
    ).first()


    if not attempt:
        return {
            "error": "Попытка не найдена"
        }


    score = 0


    for answer in data.answers:

        selected_answer = db.query(
            AnswerOption
        ).filter(
            AnswerOption.id == answer.answer_id
        ).first()


        if selected_answer.is_correct:
            score += 1


        student_answer = models.StudentAnswer(
            attempt_id=attempt_id,
            question_id=answer.question_id,
            answer_id=answer.answer_id
        )

        db.add(student_answer)


    # сохраняем результат
    attempt.score = score


    db.commit()


    return {
        "attempt_id": attempt_id,
        "score": score,
        "total": len(data.answers)
    }


@app.post("/tests/{code}/start")
def start_test(
    code: str,
    data: StartTestRequest,
    db: Session = Depends(get_db)
):

    test = db.query(
        Test
    ).filter(
        Test.access_code == code
    ).first()


    if not test:

        return {
            "error": "Тест не найден"
        }



    user = db.query(
        User
    ).filter(
        User.id == data.student_id
    ).first()



    if not user:

        return {
            "error": "Пользователь не найден"
        }




    attempt = models.TestAttempt(

        test_id=test.id,

        student_id=data.student_id

    )



    db.add(attempt)

    db.commit()

    db.refresh(attempt)



    return {

        "attempt_id": attempt.id,

        "test_id": test.id,

        "student_id": data.student_id

    }




@app.get("/attempts/{attempt_id}/result")
def get_result(
    attempt_id: int,
    db: Session = Depends(get_db)
):

    attempt = db.query(
        models.TestAttempt
    ).filter(
        models.TestAttempt.id == attempt_id
    ).first()


    if not attempt:
        return {
            "error": "Попытка не найдена"
        }


    total = db.query(
        Question
    ).filter(
        Question.test_id == attempt.test_id
    ).count()


    percent = 0

    if total > 0:
        percent = attempt.score / total * 100


    return {
        "test_id": attempt.test_id,
        "score": attempt.score,
        "total": total,
        "percent": percent
    }


@app.post(
    "/users/auth",
    response_model=UserResponse
)
def auth_user(
    data: UserAuth,
    db: Session = Depends(get_db)
):

    user = db.query(
        User
    ).filter(
        User.max_id == data.max_id
    ).first()



    if not user:


        user = User(

            max_id=data.max_id,

            username=data.username

        )


        db.add(user)

        db.commit()

        db.refresh(user)



    return user



