import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    environment: str = os.getenv("ENVIRONMENT", "development")
    frontend_url: str = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173",
    )


settings = Settings()