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
from sqlalchemy import func

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

    # leave_count / hidden_seconds читаются и пишутся сырым SQL
    # (чтобы приложение не падало, если колонок ещё нет в БД)

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
    # Ограничение времени на весь тест в минутах (None = без ограничения)
    time_limit_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
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
# Класс (например, «10-А»), принадлежит учителю
class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True)

    name = Column(String(100), nullable=False)

    teacher_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    created_at = Column(DateTime, server_default=func.now())

    teacher = relationship("User", foreign_keys=[teacher_id])

    members = relationship(
        "ClassMember",
        back_populates="class_",
        cascade="all, delete-orphan"
    )


# Ученик в классе
class ClassMember(Base):
    __tablename__ = "class_members"

    id = Column(Integer, primary_key=True)

    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    joined_at = Column(DateTime, server_default=func.now())

    # Один ученик не может быть в одном классе дважды
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_class_member"),
    )

    class_ = relationship("Class", back_populates="members")
    student = relationship("User", foreign_keys=[student_id])