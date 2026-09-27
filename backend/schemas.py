from pydantic import BaseModel



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

    creator_id: int

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