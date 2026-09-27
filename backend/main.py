from fastapi import FastAPI, Depends
from fastapi import UploadFile, File, HTTPException
import fitz  # pymupdf
from backend.gigachat_services import (
    generate_quiz_by_topic,
    generate_quiz_by_text,
    create_custom_quiz,
    generate_notes_by_topic,       # ← новое
    generate_notes_by_text,        # ← новое
)

import fitz  # pymupdf
from fastapi import UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend import models
import random
import string
from backend.models import (StudentAnswer, Test, Question, AnswerOption, User)
from fastapi.responses import FileResponse
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.schemas import (
TestCreate,
    TestResponse,
NotesRequest,
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

from backend.gigachat_services import (
    generate_quiz_by_topic,
    generate_quiz_by_text,
    create_custom_quiz,
)

from typing import Literal, Optional





class GenerateTestRequest(BaseModel):

    mode: Literal[
        "topic",
        "text",
        "custom"
    ]

    topic: Optional[str] = None

    content: Optional[str] = None

    question_count: int = 5

    questions: Optional[list] = None






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

@app.get("/smart_notes.html")
def smart_notes():
    return FileResponse("frontend/smart_notes.html")

@app.get("/test_page")
def test_page():
    return FileResponse("frontend/test_page.html")

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


@app.post(
    "/generate-test",
    response_model=GeneratedTestResponse
)
def generate_test(data: GenerateTestRequest):

    if data.mode == "topic":

        result = generate_quiz_by_topic(
            data.topic,
            data.question_count
        )

    elif data.mode == "text":

        result = generate_quiz_by_text(
            data.content,
            data.question_count
        )

    elif data.mode == "custom":

        result = create_custom_quiz(
            data.questions
        )

    else:

        return {
            "error": "Неизвестный режим"
        }


    return result

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



#Конспект

class NotesRequest(BaseModel):
    mode: Literal["topic", "text"]
    topic: Optional[str] = None
    content: Optional[str] = None


@app.post("/generate-notes")
def generate_notes(data: NotesRequest):
    if data.mode == "topic":
        if not data.topic:
            raise HTTPException(400, "Тема не указана")
        notes = generate_notes_by_topic(data.topic)

    elif data.mode == "text":
        if not data.content:
            raise HTTPException(400, "Текст не указан")
        notes = generate_notes_by_text(data.content)

    else:
        raise HTTPException(400, "Неизвестный режим")

    return {"notes": notes}


@app.post("/generate-notes-from-file")
async def generate_notes_from_file(file: UploadFile = File(...)):
    content = await file.read()
    name = (file.filename or "").lower()

    if name.endswith(".pdf"):
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
        except Exception:
            raise HTTPException(400, "Не удалось прочитать PDF")

    elif name.endswith(".txt"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("cp1251", errors="ignore")

    else:
        raise HTTPException(400, "Поддерживаются только .txt и .pdf")

    if not text.strip():
        raise HTTPException(400, "Файл пустой или это скан (текст не извлекается)")

    notes = generate_notes_by_text(text)
    return {"notes": notes}