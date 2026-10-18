from sqlalchemy import Integer, String, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base, engine


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")


def ensure_role_column() -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "role" in columns:
        return

    try:
        with engine.begin() as connection:
            if engine.dialect.name == "postgresql":
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(
                text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
            )
    except OperationalError as exc:
        raise RuntimeError(
            "Не получилось добавить колонку role в таблицу users: её держит открытой другая программа.\n"
            "Закрой pgAdmin / DBeaver и другие окна с запущенным сервером (Ctrl+C), затем запусти заново.\n"
            "Или выполни вручную в pgAdmin:\n"
            "    ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';"
        ) from exc
