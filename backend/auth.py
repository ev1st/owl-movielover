"""
Регистрация, вход и защита эндпоинтов.

Как это работает, по шагам:
1. Человек регистрируется — в базу сохраняется его почта и ХЕШ пароля (сам пароль не хранится).
2. Человек входит — сервер проверяет пароль и выдаёт ТОКЕН (JWT). Токен — это
   зашифрованный «пропуск» с id пользователя и временем, до которого он действует.
3. Браузер сам прикладывает токен к каждому следующему запросу (мы кладём его в cookie).
4. «Охранники» get_current_user и require_admin проверяют пропуск на защищённых эндпоинтах.
"""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt  # библиотека PyJWT: создаёт и проверяет токены
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.db import Session  # db.py заодно читает файл .env
from backend.models import User

router = APIRouter(prefix="/api")  # все адреса ниже начинаются с /api


# =====================================================================
# НАСТРОЙКИ (берутся из файла .env, значения по умолчанию — справа)
# =====================================================================
JWT_ALGORITHM = "HS256"  # способ подписи токена
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # токен живёт 24 часа
COOKIE_NAME = "owl_token"  # имя cookie, в которой лежит токен

# На https-сайте в .env ставим COOKIE_SECURE=true, на localhost оставляем false
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "").lower() in ("1", "true", "yes")

# Почты админов из .env через запятую: ADMIN_EMAILS=me@mail.ru,friend@mail.ru
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}

# Секретный ключ, которым подписываются токены. Кто его знает — тот может подделать токен,
# поэтому он лежит в .env и никому не показывается.
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Запасной вариант, чтобы сайт запустился: ключ на одну сессию сервера
    JWT_SECRET = secrets.token_hex(32)
    print("[auth] JWT_SECRET не задан в .env — создан временный ключ, "
          "после перезапуска сервера все токены перестанут работать.")


# =====================================================================
# ПАРОЛИ
# =====================================================================
def hash_password(password: str, salt: bytes | None = None) -> str:
    """Превращает пароль в «кашу» (хеш). Из неё нельзя вернуть пароль обратно."""
    salt = salt or os.urandom(16)  # соль — случайная добавка, чтобы одинаковые пароли давали разные хеши
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def check_password(password: str, saved_hash: str) -> bool:
    """Проверяет пароль: хешируем его с той же солью и сравниваем с сохранённым."""
    salt = bytes.fromhex(saved_hash.split("$")[0])
    return hmac.compare_digest(hash_password(password, salt), saved_hash)


# =====================================================================
# ТОКЕН (JWT)
# =====================================================================
def create_token(user: User) -> str:
    """Делает токен-пропуск для пользователя."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.user_id),  # sub — «кто это»: id пользователя
        "role": user.role,
        "iat": now,  # когда выдан
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),  # до какого времени действует
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _extract_token(request: Request) -> str | None:
    """Достаёт токен из запроса: сначала из заголовка Authorization, потом из cookie."""
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")  # заголовок выглядит так: "Bearer <токен>"
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return request.cookies.get(COOKIE_NAME)


# =====================================================================
# «ОХРАННИКИ» — подключаются к эндпоинтам через Depends(...)
# =====================================================================
def get_current_user(request: Request) -> User:
    """Охранник №1: пускает только вошедших. Возвращает пользователя из базы."""
    unauthorized = HTTPException(
        401, "Сначала войди в аккаунт, вась.", headers={"WWW-Authenticate": "Bearer"}
    )

    token = _extract_token(request)
    if not token:
        raise unauthorized  # токена нет — человек не входил

    try:
        # decode проверяет подпись и срок действия. Если токен подделан или просрочен — будет ошибка.
        payload = jwt.decode(
            token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise unauthorized

    with Session() as session:
        user = session.get(User, user_id)
    if user is None:  # аккаунт удалили — старый токен больше не годится
        raise unauthorized
    # Роль берём из базы, а не из токена: если админ сменил роль, это работает сразу.
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Охранник №2: пускает только админов (сначала проверяет, что человек вообще вошёл)."""
    if user.role != "admin":
        raise HTTPException(403, "Это только для админов, вась.")  # 403 = «ты вошёл, но тебе нельзя»
    return user


# =====================================================================
# СХЕМЫ — какие данные ждёт сервер в запросах
# =====================================================================
class RegisterData(BaseModel):
    username: str
    email: str
    password: str


class LoginData(BaseModel):
    email: str
    password: str


class RoleData(BaseModel):
    role: Literal["user", "admin"]  # любое другое значение сервер отклонит сам


# =====================================================================
# ЭНДПОИНТЫ ДЛЯ ВСЕХ
# =====================================================================
@router.post("/register", status_code=201)
def register(data: RegisterData):
    username = data.username.strip()
    email = data.email.strip().lower()
    password = data.password

    # --- проверяем, что данные нормальные ---
    if not 3 <= len(username) <= 30:
        raise HTTPException(422, "Имя пользователя: от 3 до 30 символов, вась.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
        raise HTTPException(422, "Проверь адрес электронной почты, вась.")
    if not (
        8 <= len(password) <= 128
        and re.search("[a-z]", password)
        and re.search("[A-Z]", password)
        and re.search("[0-9]", password)
    ):
        raise HTTPException(422, "Пароль: минимум 8 символов, заглавная и строчная буквы и цифра.")

    with Session() as session:
        # --- имя и почта должны быть свободны ---
        if session.scalar(select(User).where(func.lower(User.username) == username.lower())):
            raise HTTPException(409, "Такое имя уже занято, вась.")
        if session.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "Аккаунт с такой почтой уже есть, вась.")

        # Почта из списка ADMIN_EMAILS сразу становится админом, остальные — обычные пользователи
        role = "admin" if email in ADMIN_EMAILS else "user"
        session.add(
            User(username=username, email=email, password_hash=hash_password(password), role=role)
        )
        session.commit()
    return {"username": username}


@router.post("/login")
def login(data: LoginData, response: Response):
    email = data.email.strip().lower()
    with Session() as session:
        user = session.scalar(select(User).where(User.email == email))
        # Одно и то же сообщение и для неверной почты, и для неверного пароля — так безопаснее
        if not user or not check_password(data.password, user.password_hash):
            raise HTTPException(401, "Неверная почта или пароль, вась.")
        if email in ADMIN_EMAILS and user.role != "admin":  # почту добавили в ADMIN_EMAILS позже
            user.role = "admin"
            session.commit()

    token = create_token(user)
    # Кладём токен в cookie: дальше браузер сам будет присылать его с каждым запросом
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=JWT_EXPIRE_MINUTES * 60,  # сколько секунд хранить cookie
        httponly=True,  # JavaScript на странице не сможет прочитать токен (защита от кражи)
        samesite="lax",  # cookie не уходит с чужих сайтов (защита от CSRF)
        secure=COOKIE_SECURE,
        path="/",
    )
    return {
        "username": user.username,  # это поле читает фронтенд (login.js)
        "role": user.role,
        "access_token": token,  # то же самое для тех, кто хочет слать токен заголовком
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(response: Response):
    """Выход: просим браузер удалить cookie с токеном."""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"detail": "Вышли, вась."}


# =====================================================================
# ЭНДПОИНТ ДЛЯ ЛЮБОГО ВОШЕДШЕГО
# =====================================================================
@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """Показывает данные того, кто сейчас вошёл."""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


# =====================================================================
# ЭНДПОИНТЫ ТОЛЬКО ДЛЯ АДМИНОВ
# =====================================================================
@router.get("/admin/users")
def admin_list_users(_: User = Depends(require_admin)):
    """Список всех пользователей."""
    with Session() as session:
        users = session.scalars(select(User).order_by(User.user_id)).all()
    return [
        {"user_id": u.user_id, "username": u.username, "email": u.email, "role": u.role}
        for u in users
    ]


@router.patch("/admin/users/{user_id}/role")
def admin_set_role(user_id: int, data: RoleData, admin: User = Depends(require_admin)):
    """Меняет роль пользователя на user или admin."""
    if user_id == admin.user_id:
        raise HTTPException(400, "Свою роль менять нельзя, вась.")  # иначе можно случайно остаться без админов
    with Session() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(404, "Пользователь не найден, вась.")
        user.role = data.role
        session.commit()
        return {"user_id": user.user_id, "username": user.username, "role": user.role}


@router.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin: User = Depends(require_admin)):
    """Удаляет пользователя."""
    if user_id == admin.user_id:
        raise HTTPException(400, "Себя удалять нельзя, вась.")
    with Session() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(404, "Пользователь не найден, вась.")
        session.delete(user)
        session.commit()
    return {"detail": "Пользователь удалён."}
