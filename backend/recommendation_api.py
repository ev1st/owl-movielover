import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from backend.auth import get_current_user, router as auth_router
from backend.db import Base, engine
from backend.models import ensure_role_column
from backend.owl_recomender import OwlSimpleRecommender

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
CACHE_PATH = Path(__file__).resolve().parent / "translation_cache.json"
app = FastAPI(title="Owl Movie Recommender")
app.include_router(auth_router)
Base.metadata.create_all(engine)
ensure_role_column()
recommender = OwlSimpleRecommender()

TMDB_CACHE_PATH = Path(__file__).resolve().parent / "tmdb_cache.json"
TMDB_TIMEOUT = 10
tmdb_pool = ThreadPoolExecutor(max_workers=8)


TMDB_KEY = os.getenv("TMDB_API_KEY", "")
try:
    tmdb_cache: dict[str, dict[str, str]] = json.loads(TMDB_CACHE_PATH.read_text("utf-8"))
except (OSError, ValueError):
    tmdb_cache = {}


def _tmdb_russian(imdb_id: str) -> None:
    if not TMDB_KEY or imdb_id in tmdb_cache or not re.fullmatch(r"tt\d+", imdb_id):
        return
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?external_source=imdb_id&language=ru-RU"
    headers = {"accept": "application/json"}
    if TMDB_KEY.startswith("eyJ"): 
        headers["Authorization"] = f"Bearer {TMDB_KEY}"
    else: 
        url += f"&api_key={TMDB_KEY}"
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=6) as response:
            data = json.load(response)
    except Exception as exc:
        print(f"[tmdb] {imdb_id}: {type(exc).__name__}: {exc}")
        return
    found = (data.get("movie_results") or [{}])[0]
    tmdb_cache[imdb_id] = {
        "title": found.get("title") or "",
        "overview": found.get("overview") or "",
    }


blocked_until = 0.0
TRANSLATE_TIMEOUT = 25  
translator_pool = ThreadPoolExecutor(max_workers=1)  

try:
    translation_cache: dict[str, str] = json.loads(CACHE_PATH.read_text("utf-8"))
except (OSError, ValueError):
    translation_cache = {}


def _to_russian(text: str) -> str: #макс, почини это ради бога
    if not text or re.search("[а-яА-ЯёЁ]", text):
        return text
    if text in translation_cache:
        return translation_cache[text]
    global blocked_until
    if time.time() < blocked_until:  
        return text
    try:
        from deep_translator import GoogleTranslator

        translated = GoogleTranslator(source="auto", target="ru").translate(text)
        time.sleep(0.3)  
    except Exception as exc:
        if type(exc).__name__ == "TooManyRequests":
            blocked_until = time.time() + 600
            print("[перевод] Google просит подождать, перевод отключён на 10 минут")
        else:
            print(f"[перевод] не получилось: {type(exc).__name__}: {exc}")
        return text
    if translated:
        translation_cache[text] = translated
        return translated
    return text

class RecommendationRequest(BaseModel):
    mode: str = "free_text"
    message: str | None = Field(default=None, max_length=1000)
    genre: str | None = Field(default=None, max_length=100)
    atmosphere: str | None = Field(default=None, max_length=150)
    country: str | None = Field(default=None, max_length=100)
    actor: str | None = Field(default=None, max_length=150)
    year_from: int | None = Field(default=None, ge=1888, le=2100)
    year_to: int | None = Field(default=None, ge=1888, le=2100)
    min_rating: float | None = Field(default=None, ge=0, le=10)
    limit: int = Field(default=20, ge=1, le=20)

    @field_validator("message", "genre", "atmosphere", "country", "actor")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class MovieRecommendation(BaseModel):
    movie_name: str
    year: int | None
    genres: list[str]
    rating: float
    atmospheres: list[str]
    actors: list[str]
    description: str
    similarity: float
    explanation: str


class RecommendationResponse(BaseModel):
    recommendations: list[MovieRecommendation]
    preferences: dict[str, Any]


GENRE_ALIASES = (
    (r"ужас|страш|хоррор", "horror"),
    (r"комед|смеш|весел", "comedy"),
    (r"детектив|загад|тайн", "mystery"),
    (r"драм|груст", "drama"),
    (r"романт|любов", "romance"),
    (r"фантаст|космос", "sci-fi"),
    (r"приключ", "adventure"),
    (r"боевик|экшен", "action"),
    (r"криминал", "crime"),
    (r"мульт|анимац", "animation"),
    (r"фэнтези|волшеб", "fantasy"),
)
ATMOSPHERE_ALIASES = (
    (r"уют|комфорт", "уют"),
    (r"весел|смеш|радост", "весел"),
    (r"пуга|страш|жутк", "пуг"),
    (r"мрач|темн", "мрач"),
    (r"напряж|триллер|саспенс", "напряж"),
    (r"романт|нежн", "романт"),
    (r"легк|ненапряж", "легк"),
    (r"загад|тайн", "загад"),
    (r"приключ", "приключ"),
    (r"волшеб|фэнтези", "волшеб"),
    (r"новогод|рождеств", "новогод"),
    (r"вдохнов|мотивир", "вдохнов"),
    (r"эмоцион|душев", "эмоцион"),
    (r"футурист|будущ", "футурист"),
)


def _split_tags(value: object) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    return [tag.strip() for tag in value.split("|") if tag.strip()]


def _find_category(
    message: str,
    options: list[str],
    aliases: tuple[tuple[str, str], ...],
) -> str | None:
    normalized = message.casefold()
    for value in options:
        if value.casefold() in normalized:
            return value
    for pattern, alias in aliases:
        if re.search(pattern, normalized):
            for value in options:
                if alias in value.casefold():
                    return value
    return None


def _infer_preferences(message: str) -> dict[str, object]:
    normalized = message.casefold()
    options = recommender.get_options()
    preferences: dict[str, object] = {
        "genre": _find_category(normalized, options["genres"], GENRE_ALIASES),
        "atmosphere": _find_category(
            normalized,
            options["atmospheres"],
            ATMOSPHERE_ALIASES,
        ),
        "country": None,
        "actor": None,
        "year_from": None,
        "year_to": None,
        "min_rating": None,
    }
    if recommender.actors:
        preferences["actor"] = next(
            (
                actor
                for actor in sorted(recommender.actors, key=len, reverse=True)
                if re.search(
                    rf"(?<!\w){re.escape(actor.casefold())}(?!\w)",
                    normalized,
                )
            ),
            None,
        )

    year_range = re.search(
        r"(?:с|от|from)\s*(18\d{2}|19\d{2}|20\d{2}|21\d{2})"
        r"\s*(?:по|до|[-–]|to)\s*(18\d{2}|19\d{2}|20\d{2}|21\d{2})",
        normalized,
    )
    if year_range:
        preferences["year_from"] = int(year_range.group(1))
        preferences["year_to"] = int(year_range.group(2))
    else:
        after_year = re.search(
            r"(?:после|позже|с|after|since|later than)\s*"
            r"(18\d{2}|19\d{2}|20\d{2}|21\d{2})",
            normalized,
        )
        before_year = re.search(
            r"(?:до|раньше|before|earlier than)\s*"
            r"(18\d{2}|19\d{2}|20\d{2}|21\d{2})",
            normalized,
        )
        single_year = re.search(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b", normalized)
        if after_year:
            preferences["year_from"] = int(after_year.group(1)) + 1
        if before_year:
            preferences["year_to"] = int(before_year.group(1)) - 1
        if single_year and not after_year and not before_year:
            preferences["year_from"] = int(single_year.group(1))
            preferences["year_to"] = int(single_year.group(1))

    rating = re.search(
        r"(?:imdb|мдб|рейтинг|оценк\w*|не ниже|выше)\s*"
        r"(?:от|не ниже|выше|above|at least|>=|>|:)?\s*"
        r"(10(?:[.,]0)?|[0-9](?:[.,][0-9])?)",
        normalized,
    )
    if rating:
        preferences["min_rating"] = float(rating.group(1).replace(",", "."))
    return preferences


@app.get("/api/options", dependencies=[Depends(get_current_user)])
def get_options() -> dict[str, object]:
    return recommender.get_options()


@app.post(
    "/api/recommendations",
    response_model=RecommendationResponse,
    dependencies=[Depends(get_current_user)],
)
def get_recommendations(
    request: RecommendationRequest,
) -> RecommendationResponse:
    if request.mode == "free_text":
        if not request.message:
            raise HTTPException(status_code=422, detail="Опиши, какой фильм хочется.")
        preferences = _infer_preferences(request.message)
    elif request.mode == "survey":
        preferences = {
            "genre": request.genre,
            "atmosphere": request.atmosphere,
            "country": request.country,
            "actor": request.actor,
            "year_from": request.year_from,
            "year_to": request.year_to,
            "min_rating": request.min_rating,
        }
    else:
      raise HTTPException(status_code=422, detail="Неизвестный режим поиска.")

    try:
        results = recommender.recommend(preferences, top_n=request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    rows = results.to_dict(orient="records")

    wait(
        [tmdb_pool.submit(_tmdb_russian, str(r["movie_id"])) for r in rows],
        timeout=TMDB_TIMEOUT,
    )
    for row in rows:
        info = tmdb_cache.get(str(row["movie_id"]), {})
        if info.get("title"):
            row["movie_name"] = info["title"]
        if info.get("overview"):
            row["description"] = recommender._short_description(info["overview"])

    texts = [
        str(r[k]) for r in rows for k in ("movie_name", "description")
        if not re.search("[а-яА-ЯёЁ]", str(r[k]))
    ]
    wait([translator_pool.submit(_to_russian, t) for t in texts], timeout=TRANSLATE_TIMEOUT)
    for path, cache in ((CACHE_PATH, translation_cache), (TMDB_CACHE_PATH, tmdb_cache)):
        try:
            path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        except (OSError, RuntimeError):
            pass

    movies: list[MovieRecommendation] = []
    for row in rows:
        row["movie_name"] = translation_cache.get(str(row["movie_name"]), row["movie_name"])
        row["description"] = translation_cache.get(str(row["description"]), row["description"])
        year = None if pd.isna(row["year"]) else int(row["year"])
        movies.append(
            MovieRecommendation(
                movie_name=str(row["movie_name"]),
                year=year,
                genres=_split_tags(row["genres_str"]),
                rating=float(row["rating"]),
                atmospheres=_split_tags(row["atmosphere_str"]),
                actors=_split_tags(row["stars_str"]),
                description=str(row["description"]),
                similarity=round(float(row["similarity"]), 3),
                explanation=str(row["explanation"]),
            )
        )

    kolobok = MovieRecommendation( #ЭТО НИ ЗА ЧТО НЕ УБИРАЙ!!!!! 
        movie_name="Последний богатырь. Колобок",
        year=2026,
        genres=["Animation", "Family"],
        rating=10.0,
        atmospheres=["сказочное", "доброе", "семейное"],
        actors=[],
        description=(
            "Самый крутой современный фильм, вась "
            "История Колобка: с какой коварной целью его испекли, как ему удалось сбежать, как он скитался и попал в банду разбойников, а потом поневоле стал напарником неудачливого пекаря Тихона и необычной девушки."
        ),
        similarity=1.0,
        explanation="ЛУЧШИЙ фильм, обязательно посмотри, вась, верх киноиндустрии.",
    )
    movies = [kolobok, *movies[: max(0, request.limit - 1)]]

    return RecommendationResponse(
        recommendations=movies,
        preferences=preferences,
    )


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
