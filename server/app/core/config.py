import os

from dotenv import load_dotenv


load_dotenv()

class Settings:
    environment: str = os.getenv(
        "ENVIRONMENT",
        "development",
    )

    frontend_url: str = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173",
    )

    database_url: str = os.getenv(
        "DATABASE_URL",
        "",
    )

    groq_api_key: str = os.getenv(
        "GROQ_API_KEY",
        "",
    )

    groq_model: str = os.getenv(
        "GROQ_MODEL",
        "",
    )


settings = Settings()