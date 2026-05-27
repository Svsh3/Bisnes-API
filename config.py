import os

# Bothost читает переменные из своей панели (Env Variables)
# Локально — из .env файла (если есть)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # на Bothost dotenv не нужен


class Config:
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
    OWNER_ID: int = int(os.environ.get("OWNER_ID", "0"))
    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OFFLINE_THRESHOLD: int = int(os.environ.get("OFFLINE_THRESHOLD", "30"))  # секунд

    @classmethod
    def validate(cls):
        errors = []
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN не задан")
        if not cls.OWNER_ID:
            errors.append("OWNER_ID не задан")
        if not cls.OPENROUTER_API_KEY:
            errors.append("OPENROUTER_API_KEY не задан")
        if errors:
            raise EnvironmentError(
                "❌ Отсутствуют переменные окружения:\n" + "\n".join(f"  • {e}" for e in errors)
            )
