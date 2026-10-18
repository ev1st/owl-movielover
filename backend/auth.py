import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.db import Session 
from backend.models import User

router = APIRouter(prefix="/api") 

JWT_ALGORITHM = "HS256" 
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
COOKIE_NAME = "owl_token"

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "").lower() in ("1", "true", "yes")

ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    print("[auth] JWT_SECRET не задан в .env — создан временный ключ, "
          "после перезапуска сервера все токены перестанут работать.")


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)  
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def check_password(password: str, saved_hash: str) -> bool:
    salt = bytes.fromhex(saved_hash.split("$")[0])
    return hmac.compare_digest(hash_password(password, salt), saved_hash)


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.user_id),
        "role": user.role,
        "iat": now, 
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request) -> User:
    unauthorized = HTTPException(
        401, "Сначала войди в аккаунт, вась.", headers={"WWW-Authenticate": "Bearer"}
    )

    token = _extract_token(request)
    if not token:
        raise unauthorized

    try:
        payload = jwt.decode(
            token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise unauthorized

    with Session() as session:
        user = session.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Это только для админов, вась.") 
    return user


class RegisterData(BaseModel):
    username: str
    email: str
    password: str


class LoginData(BaseModel):
    email: str
    password: str


class RoleData(BaseModel):
    role: Literal["user", "admin"]


@router.post("/register", status_code=201)
def register(data: RegisterData):
    username = data.username.strip()
    email = data.email.strip().lower()
    password = data.password

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
        if session.scalar(select(User).where(func.lower(User.username) == username.lower())):
            raise HTTPException(409, "Такое имя уже занято, вась.")
        if session.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "Аккаунт с такой почтой уже есть, вась.")

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
        if not user or not check_password(data.password, user.password_hash):
            raise HTTPException(401, "Неверная почта или пароль, вась.")
        if email in ADMIN_EMAILS and user.role != "admin": 
            user.role = "admin"
            session.commit()

    token = create_token(user)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=JWT_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )
    return {
        "username": user.username,
        "role": user.role,
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"detail": "Вышли, вась."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


@router.get("/admin/users")
def admin_list_users(_: User = Depends(require_admin)):
    with Session() as session:
        users = session.scalars(select(User).order_by(User.user_id)).all()
    return [
        {"user_id": u.user_id, "username": u.username, "email": u.email, "role": u.role}
        for u in users
    ]


@router.patch("/admin/users/{user_id}/role")
def admin_set_role(user_id: int, data: RoleData, admin: User = Depends(require_admin)):
    if user_id == admin.user_id:
        raise HTTPException(400, "Свою роль менять нельзя, вась.")
    with Session() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(404, "Пользователь не найден, вась.")
        user.role = data.role
        session.commit()
        return {"user_id": user.user_id, "username": user.username, "role": user.role}


@router.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin: User = Depends(require_admin)):
    if user_id == admin.user_id:
        raise HTTPException(400, "Себя удалять нельзя, вась.")
    with Session() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(404, "Пользователь не найден, вась.")
        session.delete(user)
        session.commit()
    return {"detail": "Пользователь удалён."}
