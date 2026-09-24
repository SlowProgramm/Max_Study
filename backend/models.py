from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import relationship
from backend.database import Base


# Пользователи MAX
class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True
    )

    max_id = Column(
        BigInteger,
        unique=True,
        nullable=False
    )


    username = Column(
        String,
        nullable=False
    )

# Варианты ответов
class AnswerOption(Base):

    __tablename__ = "answer_options"


    id = Column(
        Integer,
        primary_key=True
    )


    question_id = Column(
        Integer,
        ForeignKey("questions.id"),
        nullable=False
    )


    text = Column(
        String,
        nullable=False
    )


    is_correct = Column(
        Boolean,
        default=False
    )


    question = relationship(
        "Question",
        back_populates="answers"
    )

# Попытка прохождения теста
class TestAttempt(Base):

    __tablename__ = "test_attempts"


    id = Column(
        Integer,
        primary_key=True
    )


    test_id = Column(
        Integer,
        ForeignKey("tests.id"),
        nullable=False
    )


    student_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )


    start_at = Column(
        DateTime
    )


    end_at = Column(
        DateTime
    )


    score = Column(
        Integer
    )

class Test(Base):

    __tablename__ = "tests"


    id = Column(
        Integer,
        primary_key=True
    )


    creator_id = Column(
        Integer,
        ForeignKey("users.id")
    )


    title = Column(String)

    description = Column(Text)

    access_code = Column(String)


    questions = relationship(
        "Question",
        back_populates="test"
    )
class Question(Base):

    __tablename__ = "questions"


    id = Column(
        Integer,
        primary_key=True
    )


    test_id = Column(
        Integer,
        ForeignKey("tests.id"),
        nullable=False
    )


    text = Column(
        Text,
        nullable=False
    )


    order_number = Column(
        Integer
    )


    test = relationship(
        "Test",
        back_populates="questions"
    )


    answers = relationship(
        "AnswerOption",
        back_populates="question"
    )