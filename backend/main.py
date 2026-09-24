from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend import models
import random
import string
from backend.schemas import (TestCreate, TestResponse, QuestionCreate,  QuestionResponse, AnswerOptionCreate,
    AnswerOptionResponse, QuestionPublic, QuestionResponse, TestPublic)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import joinedload



app = FastAPI(
    title="MAX Study"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# создание бд
Base.metadata.create_all(
    bind=engine
)


# подключение к базе
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# генерация серкетного кода
def generate_code():
    return "".join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=6
        )
    )


# Создать тест
@app.post("/tests", response_model=TestResponse)

def create_test(test: TestCreate, db: Session = Depends(get_db)):
    new_test = models.Test(
        creator_id=1,
        title=test.title,
        description=test.description,
        access_code=generate_code()
    )

    db.add(new_test)
    db.commit()
    db.refresh(new_test)


    return new_test

@app.post(
    "/tests/{test_id}/questions",
    response_model=QuestionResponse
)
def create_question(
    test_id: int,
    question: QuestionCreate,
    db: Session = Depends(get_db)
):

    new_question = models.Question(
        test_id=test_id,
        text=question.text,
        order_number=question.order_number

    )


    db.add(new_question)
    db.commit()
    db.refresh(new_question)
    return new_question

@app.post(
    "/questions/{question_id}/answers",
    response_model=AnswerOptionResponse
)
def create_answer(
    question_id: int,
    answer: AnswerOptionCreate,
    db: Session = Depends(get_db)
):

    new_answer = models.AnswerOption(

        question_id=question_id,

        text=answer.text,

        is_correct=answer.is_correct

    )


    db.add(new_answer)

    db.commit()

    db.refresh(new_answer)


    return new_answer

@app.get(
    "/tests/code/{code}",
    response_model=TestPublic
)
def get_test_by_code(
    code: str,
    db: Session = Depends(get_db)
):

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