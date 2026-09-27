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


