import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Настройки лежат в файле .env в корне проекта
load_dotenv(Path(__file__).resolve().parent.parent / ".env", encoding="utf-8-sig")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Не найден DATABASE_URL. Создай файл .env в корне проекта (смотри .env.example)."
    )

engine = create_engine(DATABASE_URL)
Session = sessionmaker(engine)


class Base(DeclarativeBase):
    pass
