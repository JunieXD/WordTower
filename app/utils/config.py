import os


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:123456@localhost:5432/wordtower"
    )

    SECRET_KEY: str = os.getenv("SECRET_KEY", "wordtower")

settings = Settings()
