# owl.movielover

## Настройка (один раз)

1. Установи PostgreSQL и создай пустую базу `users_db`.
2. Скопируй `.env.example` в `.env` (в корне проекта) и впиши пароль и порт PostgreSQL.
   Ключ `TMDB_API_KEY` нужен для русских названий и описаний (бесплатно на themoviedb.org), его можно не указывать.
3. Установи библиотеки:
   ```
   pip install -r req.txt
   ```

## Запуск

Из корня проекта:
```
uvicorn backend.recommendation_api:app --reload
```
Сайт: http://127.0.0.1:8000

После изменения `.env` сервер нужно перезапустить.

## Файлы бэкенда

- `backend/db.py` — подключение к PostgreSQL
- `backend/models.py` — таблица `users`
- `backend/auth.py` — регистрация и вход
- `backend/recommendation_api.py` — API фильмов и раздача сайта
- `backend/owl_recomender.py` — подбор фильмов
