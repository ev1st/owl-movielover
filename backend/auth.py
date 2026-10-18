import hashlib
import hmac
import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.db import Session
from backend.models import User

router = APIRouter(prefix="/api")


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def check_password(password: str, saved_hash: str) -> bool:
    salt = bytes.fromhex(saved_hash.split("$")[0])
    return hmac.compare_digest(hash_password(password, salt), saved_hash)


class RegisterData(BaseModel):
    username: str
    email: str
    password: str


class LoginData(BaseModel):
    email: str
    password: str


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

        session.add(User(username=username, email=email, password_hash=hash_password(password)))
        session.commit()
    return {"username": username}


@router.post("/login")
def login(data: LoginData):
    with Session() as session:
        user = session.scalar(select(User).where(User.email == data.email.strip().lower()))

    if not user or not check_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверная почта или пароль, вась.")
    return {"username": user.username}
