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

    # Temporary development configuration.
    dev_user_id: str = os.getenv("DEV_USER_ID", "")
    dev_policy_id: str = os.getenv("DEV_POLICY_ID", "")


settings = Settings()