import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash"
    )

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv(
        "OPENAI_MODEL",
        "gpt-5-mini" 
    )

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    CLAUDE_MODEL = os.getenv(
        "CLAUDE_MODEL",
        "claude-sonnet-4-5"
    )

    DB_URL = os.getenv(
        "DB_URL",
        "sqlite:///revenue_recovery.db"
    )

    TIME_COMPRESSION = int(
        os.getenv("TIME_COMPRESSION", "30")
    )

    DEMO_PHONE_NUMBER = os.getenv("DEMO_PHONE_NUMBER", "")
    NOTIFY_SMS = os.getenv("NOTIFY_SMS", "true").lower()
    NOTIFY_WHATSAPP = os.getenv("NOTIFY_WHATSAPP", "false").lower()


settings = Settings()