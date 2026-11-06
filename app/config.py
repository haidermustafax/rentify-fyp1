import os
from dotenv import load_dotenv

load_dotenv()


def required_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured in .env.")
    return value


class Settings:
    DB_HOST: str = required_setting("DB_HOST")
    DB_USER: str = required_setting("DB_USER")
    DB_PASSWORD: str = required_setting("DB_PASSWORD")
    DB_NAME: str = required_setting("DB_NAME")
    SECRET_KEY: str = required_setting("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))

settings = Settings()

if len(settings.SECRET_KEY) < 32:
    raise ValueError("SECRET_KEY must contain at least 32 characters.")
