from pydantic import BaseModel

from fastapi import UploadFile, File, HTTPException
import fitz  # pymupdf

# =========================
# ТЕСТЫ
# =========================

class TestCreate(BaseModel):

    title: str

    description: str | None = None

    creator_id: int



class TestResponse(BaseModel):

    id: int

    title: str

    description: str | None

    access_code: str


    class Config:
        from_attributes = True




# =========================
# ВОПРОСЫ
# =========================

class QuestionCreate(BaseModel):

    text: str

    order_number: int | None = None



class QuestionResponse(BaseModel):

    id: int

    test_id: int

    text: str

    order_number: int | None


    class Config:
        from_attributes = True





# =========================
# ОТВЕТЫ
# =========================

class AnswerOptionCreate(BaseModel):

    text: str

    is_correct: bool = False



class AnswerOptionResponse(BaseModel):

    id: int

    question_id: int

    text: str

    is_correct: bool


    class Config:
        from_attributes = True





# =========================
# ПУБЛИЧНЫЙ ТЕСТ
# =========================

class AnswerOptionPublic(BaseModel):

    id: int

    text: str


    class Config:
        from_attributes = True





class QuestionPublic(BaseModel):

    id: int

    text: str

    answers: list[AnswerOptionPublic] = []


    class Config:
        from_attributes = True





class TestPublic(BaseModel):

    id: int

    title: str

    description: str | None

    subject: str | None = None

    time_limit_minutes: int | None = None

    time_limit_seconds: int | None = None

    is_draft: bool = False

    questions: list[QuestionPublic] = []


    class Config:
        from_attributes = True





# =========================
# СОХРАНЕНИЕ AI ТЕСТА
# =========================

class AnswerCreate(BaseModel):

    text: str

    is_correct: bool





class QuestionSave(BaseModel):

    text: str

    explanation: str | None = None

    answers: list[AnswerCreate]





class SaveTestRequest(BaseModel):

    title: str

    description: str | None = None

    subject: str | None = None

    # Устарело: создатель берётся из проверенных данных MAX, значение игнорируется.
    creator_id: int | None = None

    # Время: минуты + секунды (итого в секундах на бэке)
    time_limit_minutes: int | None = None
    time_limit_seconds: int | None = None

    is_draft: bool = False
    # сразу разослать уведомление ученикам классов
    notify: bool = False
    # опционально: конкретный class_id; если None — все классы учителя
    class_id: int | None = None
    class_ids: list[int] | None = None
    # Макс. попыток (1 по умолчанию; 0 или null = без лимита)
    max_attempts: int | None = 1

    questions: list[QuestionSave]





# =========================
# ПРОХОЖДЕНИЕ ТЕСТА
# =========================

class StudentAnswerResponse(BaseModel):

    id: int

    text: str





class StudentQuestionResponse(BaseModel):

    id: int

    text: str

    answers: list[StudentAnswerResponse]





class StudentTestResponse(BaseModel):

    id: int

    title: str

    questions: list[StudentQuestionResponse]


    class Config:
        from_attributes = True





class StudentAnswerCreate(BaseModel):

    question_id: int

    answer_id: int





class SubmitTestRequest(BaseModel):

    answers: list[StudentAnswerCreate]

    # Антисписывание (опционально — старые клиенты могут не присылать)
    leave_count: int | None = 0
    hidden_seconds: int | None = 0





# =========================
# ГЕНЕРАЦИЯ ТЕСТА
# =========================

class GeneratedAnswer(BaseModel):

    text: str

    is_correct: bool





class GeneratedQuestion(BaseModel):

    text: str

    explanation: str | None = None

    answers: list[GeneratedAnswer]





class GeneratedTestResponse(BaseModel):

    title: str

    questions: list[GeneratedQuestion]

# d



# =========================
# ПОЛЬЗОВАТЕЛИ MAX
# =========================

class UserCreate(BaseModel):

    max_id: int

    username: str





class UserAuth(BaseModel):

    max_id: int

    username: str





class UserResponse(BaseModel):

    id: int

    max_id: int

    username: str


    class Config:
        from_attributes = True





# =========================
# СТАРТ ТЕСТА
# =========================

class StartTestRequest(BaseModel):

    student_id: int



class StudentOut(BaseModel):
    id: int
    max_id: int
    username: str

    class Config:
        from_attributes = True


class ClassOut(BaseModel):
    id: int
    name: str
    student_count: int = 0

    class Config:
        from_attributes = True


class CreateClassIn(BaseModel):
    name: str


class AddStudentIn(BaseModel):
    max_id: int
    class_id: int



class AttemptHistoryItem(BaseModel):
    attempt_id: int
    test_id: int
    test_title: str
    score: int | None
    total: int
    percent: float | None
    leave_count: int = 0
    hidden_seconds: int = 0


# =========================
# ЖУРНАЛ / АНАЛИТИКА
# =========================

class JournalStudentScore(BaseModel):
    student_id: int
    username: str
    score: int | None
    total: int
    percent: float | None
    leave_count: int = 0
    hidden_seconds: int = 0
    attempt_id: int | None = None


class JournalTestItem(BaseModel):
    test_id: int
    title: str
    access_code: str
    question_count: int
    attempt_count: int
    created_at: str | None = None


class GradebookScore(BaseModel):
    test_id: int
    score: int | None
    total: int
    percent: float | None
    attempt_id: int | None = None


class GradebookStudent(BaseModel):
    student_id: int
    username: str
    max_id: int | None = None
    scores: list[GradebookScore] = []


class GradebookResponse(BaseModel):
    tests: list[JournalTestItem]
    students: list[GradebookStudent]


class QuestionStat(BaseModel):
    question_id: int
    text: str
    correct_count: int
    wrong_count: int
    total_answers: int
    correct_percent: float


class TestAnalytics(BaseModel):
    test_id: int
    title: str
    question_count: int
    attempt_count: int
    avg_percent: float | None
    hardest_question: QuestionStat | None
    questions: list[QuestionStat]
    students: list[JournalStudentScore]


class StudentAttemptDetail(BaseModel):
    attempt_id: int
    test_id: int
    test_title: str
    score: int | None
    total: int
    percent: float | None
    leave_count: int = 0
    hidden_seconds: int = 0
    wrong_answers: list[dict] = []
    hardest_question_text: str | None = None


class DraftTestItem(BaseModel):
    test_id: int
    title: str
    description: str | None = None
    subject: str | None = None
    access_code: str
    time_limit_seconds: int | None = None
    created_at: str | None = None


class NotifyTestRequest(BaseModel):
    # Один класс (обратная совместимость)
    class_id: int | None = None
    # Несколько классов: если задан — уведомляются только они
    class_ids: list[int] | None = None


class TestEntryInfo(BaseModel):
    id: int
    title: str
    description: str | None = None
    subject: str | None = None
    access_code: str
    time_limit_seconds: int | None = None
    question_count: int = 0


# =========================
# ЗАПЛАНИРОВАННЫЕ ТЕСТЫ (анонсы)
# =========================

class ScheduledTestCreate(BaseModel):
    title: str
    subject: str
    description: str | None = None
    scheduled_date: str  # YYYY-MM-DD
    materials_text: str | None = None
    class_id: int | None = None  # если None — единственный класс учителя


class ScheduledTestOut(BaseModel):
    id: int
    title: str
    subject: str
    description: str | None = None
    scheduled_date: str  # DD.MM.YYYY
    materials_text: str | None = None
    class_id: int
    class_name: str | None = None
    created_at: str | None = None
    notified_day_before: bool = False

    class Config:
        from_attributes = True


# Редактирование черновика (полная замена вопросов)
class UpdateDraftRequest(BaseModel):
    title: str
    description: str | None = None
    subject: str | None = None
    time_limit_minutes: int | None = None
    time_limit_seconds: int | None = None
    max_attempts: int | None = 1
    questions: list[QuestionSave]
