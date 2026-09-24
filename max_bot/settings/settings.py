import os
from dotenv import load_dotenv

load_dotenv()


class Settings:

    max_api_key = os.getenv("MAX_TOKEN")
    app_url = os.getenv("APP_URL")
    max_bot_id = int(os.getenv("MAX_BOT_ID"))

settings = Settings()
