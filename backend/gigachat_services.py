import json
import os
from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

load_dotenv()
GIGACHAT_TOKEN = os.getenv('GIGACHAT_TOKEN')



def create_topic_prompt(topic: str, question_count: int):
    return f"""
    Ты профессиональный преподаватель.
    Создай тест по теме:
    {topic}
    Количество вопросов:
    {question_count}
    Требования:
    - каждый вопрос должен иметь 3-4 варианта ответа;
    - только один правильный ответ;
    - вопросы должны проверять понимание темы;
    - добавь краткое объяснение правильного ответа.
    Верни только JSON.
    Формат:
    {{
        "title": "название теста",
        "questions": [
            {{
                "text": "текст вопроса",
    
                "answers": [
                    {{
                        "text": "вариант ответа",
                        "is_correct": false
                    }}
                ],
    
                "explanation": "объяснение"
            }}
        ]
    }}
"""

def create_text_prompt(text: str, question_count: int):
    return f"""
        Ты профессиональный преподаватель.
        Создай тест только на основе этого материала:
        {text}
        Количество вопросов:
        {question_count}
        СТРОГИЕ ПРАВИЛА:  
        - не добавляй информацию, которой нет в тексте;
        - каждый вопрос имеет 2-4 ответа;
        - только один правильный;
        - добавь объяснение.
        Верни только JSON.
        Формат:
        {{
            "title": "название теста",
            "questions": [
                {{
                    "text": "текст вопроса",
                    "answers": [
                        {{
                            "text": "вариант",
                            "is_correct": false
                        }}
                    ],
                    "explanation": "объяснение"
                }}
            ]
        }}
"""


def get_gigachat():
    return GigaChat(
        base_url="https://api.giga.chat/v1",
        credentials=GIGACHAT_TOKEN,
        scope="GIGACHAT_API_PERS",
        verify_ssl_certs=False,
        timeout=300
    )

def ask_gigachat(prompt: str, user_content: str):
    client = get_gigachat()
    messages = [
        Messages(role=MessagesRole.SYSTEM,content=prompt),
        Messages(role=MessagesRole.USER,content=user_content)
    ]
    chat = Chat(model="GigaChat-3-Ultra", messages=messages)
    response = client.chat(chat)
    content = response.choices[0].message.content
    # print(content)
    return json.loads(content)


def generate_quiz_by_topic(topic: str, question_count: int):
    prompt = create_topic_prompt(topic,question_count)
    return ask_gigachat(prompt,topic)


def generate_quiz_by_text(text: str, question_count: int):
    prompt = create_text_prompt(text,question_count)
    return ask_gigachat(prompt, text)


def create_custom_quiz(questions: list):
    return {"title": "Пользовательский тест",
        "questions": questions}

def create_notes_prompt_by_topic(topic: str) -> str:
    return """Ты — опытный преподаватель. Составь подробный структурированный конспект по заданной теме для самостоятельного изучения.

Требования:
- Начни с заголовка темы (## Заголовок).
- Раскрой основные понятия и определения.
- Приведи ключевые факты, формулы, даты — если применимо.
- Разбери логику и связи между идеями.
- Дай 1–3 примера.
- В конце — блок «## Вопросы для самопроверки» с 3–5 вопросами.

Формат ответа — markdown:
- заголовки через ## и ###
- ключевые термины выделяй **жирным**
- списки через "- " или "1. "

Пиши на русском языке. Без воды, только по делу.
Не возвращай JSON. Только markdown-текст конспекта."""


def create_notes_prompt_by_text(text: str) -> str:
    return """Ты — опытный преподаватель. На основе предоставленного текста составь подробный структурированный конспект для изучения.

СТРОГИЕ ПРАВИЛА:
- Используй только информацию из текста. Не добавляй ничего от себя.
- Определи главную тему текста и вынеси её в заголовок (## Заголовок).
- Структурируй материал по смысловым блокам (## / ###).
- Сохрани важные детали, определения, примеры.
- В конце — блок «## Вопросы для самопроверки» с 3–5 вопросами по материалу.

Формат ответа — markdown:
- заголовки через ## и ###
- ключевые термины выделяй **жирным**
- списки через "- " или "1. "

Пиши на русском языке.
Не возвращай JSON. Только markdown-текст конспекта."""


def ask_gigachat_text(system_prompt: str, user_content: str) -> str:
    """Как ask_gigachat, но возвращает сырой текст без json.loads."""
    client = get_gigachat()
    messages = [
        Messages(role=MessagesRole.SYSTEM, content=system_prompt),
        Messages(role=MessagesRole.USER, content=user_content)
    ]
    chat = Chat(model="GigaChat-3-Ultra", messages=messages)
    response = client.chat(chat)
    return response.choices[0].message.content


def generate_notes_by_topic(topic: str) -> str:
    prompt = create_notes_prompt_by_topic(topic)
    return ask_gigachat_text(prompt, topic)


def generate_notes_by_text(text: str) -> str:
    prompt = create_notes_prompt_by_text(text)
    return ask_gigachat_text(prompt, text)

