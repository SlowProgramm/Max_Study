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

    time_limit_minutes: int | None = None

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

    # Устарело: создатель берётся из проверенных данных MAX, значение игнорируется.
    creator_id: int | None = None

    # Ограничение времени на весь тест в минутах (None / 0 = без ограничения)
    time_limit_minutes: int | None = None

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
