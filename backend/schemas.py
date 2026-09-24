from pydantic import BaseModel

class TestCreate(BaseModel):
    title: str
    description: str | None = None

class TestResponse(BaseModel):
    id: int
    title: str
    description: str | None
    access_code: str

    class Config:
        from_attributes = True

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