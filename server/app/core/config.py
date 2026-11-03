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

    # LLM provider selection
    llm_provider: str = os.getenv(
        "LLM_PROVIDER",
        "groq",
    ).strip().lower()

    # Groq configuration
    groq_api_key: str = os.getenv(
        "GROQ_API_KEY",
        "",
    )

    groq_model: str = os.getenv(
        "GROQ_MODEL",
        "llama-3.3-70b-versatile",
    )

    # Gemini configuration
    gemini_api_key: str = os.getenv(
        "GEMINI_API_KEY",
        "",
    )

    gemini_model: str = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.8-flash",
    )

    # Temporary development configuration.
    dev_user_id: str = os.getenv("DEV_USER_ID", "")
    dev_policy_id: str = os.getenv("DEV_POLICY_ID", "")

settings = Settings()