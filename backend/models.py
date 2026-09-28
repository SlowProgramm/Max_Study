from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint
)

from sqlalchemy.orm import relationship
from backend.database import Base


# Пользователи MAX
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    max_id = Column(BigInteger, unique=True, nullable=False)

    username = Column(String, nullable=False)


# Варианты ответов
class AnswerOption(Base):
    __tablename__ = "answer_options"
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    text = Column(String, nullable=False)
    is_correct = Column(Boolean, default=False)
    question = relationship(
        "Question",
        back_populates="answers"
    )


# Попытка прохождения теста
class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id = Column(Integer, primary_key=True)

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

    score = Column(Integer)


    test = relationship(
        "Test"
    )

    student = relationship(
        "User"
    )

    answers = relationship(
        "StudentAnswer"
    )


# Тест
class Test(Base):
    __tablename__ = "tests"
    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    description = Column(Text)
    access_code = Column(String)
    questions = relationship(
        "Question",
        back_populates="test"
    )


# Вопросы
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)

    test_id = Column(
        Integer,
        ForeignKey("tests.id"),
        nullable=False
    )

    text = Column(Text, nullable=False)

    explanation = Column(Text)

    order_number = Column(Integer)

    test = relationship(
        "Test",
        back_populates="questions"
    )

    answers = relationship(
        "AnswerOption",
        back_populates="question"
    )

class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id = Column(Integer, primary_key=True)

    attempt_id = Column(
        Integer,
        ForeignKey("test_attempts.id"),
        nullable=False
    )

    question_id = Column(
        Integer,
        ForeignKey("questions.id"),
        nullable=False
    )

    answer_id = Column(
        Integer,
        ForeignKey("answer_options.id"),
        nullable=False
    )


    attempt = relationship(
        "TestAttempt"
    )

    question = relationship(
        "Question"
    )

    answer = relationship(
        "AnswerOption"
    )


# Класс учителя: какие ученики к какому учителю относятся.
# Одна строка = «ученик student_id состоит в классе учителя teacher_id».
# username здесь не дублируется — он берётся из users по student_id
# (так он не устареет, если человек сменит имя в MAX).
class ClassStudent(Base):
    __tablename__ = "class_students"

    id = Column(Integer, primary_key=True)

    teacher_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Ученик не может быть добавлен к одному учителю дважды.
    __table_args__ = (
        UniqueConstraint("teacher_id", "student_id", name="uq_class_teacher_student"),
    )

    teacher = relationship("User", foreign_keys=[teacher_id])

    student = relationship("User", foreign_keys=[student_id])
