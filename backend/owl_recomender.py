from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer

import os


def _project_root() -> Path:
    return Path(os.getcwd())


PROJECT_ROOT = _project_root()
DATA_PATH = PROJECT_ROOT / "database" / "movies_for_training.csv"
COUNTRY_COLUMNS = ("country_str", "countries_str", "country", "countries")
RESULT_COLUMNS = [
    "movie_name",
    "year",
    "genres_str",
    "rating",
    "atmosphere_str",
    "stars_str",
    "description",
    "similarity",
    "explanation",
]


class OwlSimpleRecommender:
    def __init__(self, data_path: str | Path | None = None):
        csv_path = Path(data_path) if data_path is not None else DATA_PATH
        if not csv_path.is_file():
            raise FileNotFoundError(f"Файл с фильмами не найден: {csv_path}")

        df = pd.read_csv(csv_path)
        required_columns = {
            "movie_name",
            "year",
            "genres_str",
            "rating",
            "atmosphere_str",
            "description",
        }
        missing_columns = required_columns.difference(df.columns)
        if missing_columns:
            raise ValueError(
                "В CSV отсутствуют обязательные столбцы: "
                + ", ".join(sorted(missing_columns))
            )

        self.country_column = next(
            (column for column in COUNTRY_COLUMNS if column in df.columns),
            None,
        )
        defaults = {
            "genres_str": "",
            "atmosphere_str": "",
            "description": "",
            "stars_str": "",
            "rating": 0,
            "popularity": 0,
        }
        if self.country_column:
            defaults[self.country_column] = ""
        for column, default in defaults.items():
            if column not in df:
                df[column] = default
        df = df.fillna(defaults)
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0)
        df["popularity"] = pd.to_numeric(
            df["popularity"], errors="coerce"
        ).fillna(0)
        df["genres_list"] = df["genres_str"].map(self._split_tags)
        df["atmosphere_list"] = df["atmosphere_str"].map(self._split_tags)
        df["stars_list"] = df["stars_str"].map(self._split_tags)
        df["country_list"] = (
            df[self.country_column].map(self._split_tags)
            if self.country_column
            else [[] for _ in range(len(df))]
        )
        self.df = df.reset_index(drop=True)

        self.genre_mlb = self._fit_binarizer(self.df["genres_list"])
        self.atmo_mlb = self._fit_binarizer(self.df["atmosphere_list"])
        self.country_mlb = self._fit_binarizer(self.df["country_list"])
        genre_matrix = self.genre_mlb.transform(self.df["genres_list"])
        atmosphere_matrix = self.atmo_mlb.transform(self.df["atmosphere_list"])
        country_matrix = self.country_mlb.transform(self.df["country_list"])
        rating_vector = (self.df["rating"].to_numpy() / 10.0).reshape(-1, 1)

        self.X = np.hstack(
            [
                genre_matrix.astype(float),
                atmosphere_matrix.astype(float) * 1.1,
                country_matrix.astype(float) * 0.8,
                rating_vector * 0.5,
            ]
        )
        self.rating_order = np.argsort(
            self.df["rating"].to_numpy(), kind="stable"
        )
        self.sorted_ratings = self.df["rating"].to_numpy()[self.rating_order]
        self.available_years = self.df["year"].dropna()
        self.actors = sorted(
            {
                actor
                for cast in self.df["stars_list"]
                for actor in cast
            },
            key=str.casefold,
        )

    @staticmethod
    def _split_tags(value: object) -> list[str]:
        if not isinstance(value, str) or not value.strip():
            return []
        return [tag.strip() for tag in value.split("|") if tag.strip()]

    @staticmethod
    def _fit_binarizer(values: pd.Series) -> MultiLabelBinarizer:
        binarizer = MultiLabelBinarizer()
        binarizer.fit(values)
        return binarizer

    @staticmethod
    def _optional_text(value: object, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"Значение «{field}» должно быть строкой.")
        return value.strip() or None

    @staticmethod
    def _optional_year(value: object, field: str) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError(f"Значение «{field}» должно быть годом.")
        try:
            year_number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Значение «{field}» должно быть годом.") from exc
        if not year_number.is_integer():
            raise ValueError(f"Значение «{field}» должно быть целым годом.")
        year = int(year_number)
        if not 1888 <= year <= 2100:
            raise ValueError(f"Год «{field}» должен быть от 1888 до 2100.")
        return year

    @staticmethod
    def _optional_rating(value: object) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError("Минимальный IMDb-рейтинг должен быть числом.")
        try:
            rating = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Минимальный IMDb-рейтинг должен быть числом.") from exc
        if not 0 <= rating <= 10:
            raise ValueError("Минимальный IMDb-рейтинг должен быть от 0 до 10.")
        return rating

    @staticmethod
    def _encode_preference(
        value: str | None,
        binarizer: MultiLabelBinarizer,
        field: str,
    ) -> np.ndarray:
        if value is None:
            return np.zeros((1, len(binarizer.classes_)))
        if not len(binarizer.classes_):
            raise ValueError(f"В датасете нет значений для поля «{field}».")

        normalized = value.casefold()
        matching_tags = {
            tag.casefold(): tag for tag in binarizer.classes_
        }
        if normalized not in matching_tags:
            choices = ", ".join(binarizer.classes_)
            raise ValueError(
                f"Неизвестное значение «{value}» для поля «{field}». "
                f"Допустимые значения: {choices}"
            )
        return binarizer.transform([[matching_tags[normalized]]])

    def get_options(self) -> dict[str, object]:
        years = self.available_years
        return {
            "genres": self.genre_mlb.classes_.tolist(),
            "atmospheres": self.atmo_mlb.classes_.tolist(),
            "countries": self.country_mlb.classes_.tolist(),
            "has_country_data": self.country_column is not None,
            "year_min": int(years.min()) if not years.empty else None,
            "year_max": int(years.max()) if not years.empty else None,
        }

    def recommend(
        self,
        survey: Mapping[str, object],
        top_n: int = 20,
    ) -> pd.DataFrame:
        if (
            isinstance(top_n, bool)
            or not isinstance(top_n, int)
            or not 1 <= top_n <= 20
        ):
            raise ValueError("Количество рекомендаций должно быть от 1 до 20.")

        genre = self._optional_text(survey.get("genre"), "жанр")
        atmosphere = self._optional_text(survey.get("atmosphere"), "вайб")
        country = self._optional_text(survey.get("country"), "страна")
        actor = self._optional_text(survey.get("actor"), "актёр")
        year_from = self._optional_year(survey.get("year_from"), "год начала")
        year_to = self._optional_year(survey.get("year_to"), "год окончания")
        min_rating = self._optional_rating(survey.get("min_rating"))

        if year_from is not None and year_to is not None and year_from > year_to:
            raise ValueError("Год начала не может быть больше года окончания.")
        if country and not self.country_column:
            raise ValueError(
                "В CSV нет данных о стране производства, поэтому фильтр "
                "по стране пока недоступен."
            )

        genre_vector = self._encode_preference(
            genre, self.genre_mlb, "жанр"
        ).astype(float)
        atmosphere_vector = (
            self._encode_preference(atmosphere, self.atmo_mlb, "вайб").astype(float)
            * 1.1
        )
        country_vector = (
            self._encode_preference(country, self.country_mlb, "страна").astype(float)
            * 0.8
        )

        mask = pd.Series(True, index=self.df.index)
        if genre:
            mask &= self.df["genres_list"].map(
                lambda tags: genre.casefold()
                in {tag.casefold() for tag in tags}
            )
        if atmosphere:
            mask &= self.df["atmosphere_list"].map(
                lambda tags: atmosphere.casefold()
                in {tag.casefold() for tag in tags}
            )
        if country:
            mask &= self.df["country_list"].map(
                lambda tags: country.casefold()
                in {tag.casefold() for tag in tags}
            )
        if actor:
            if actor.casefold() not in {name.casefold() for name in self.actors}:
                raise ValueError(f"Актёр «{actor}» не найден в датасете.")
            mask &= self.df["stars_list"].map(
                lambda tags: actor.casefold()
                in {tag.casefold() for tag in tags}
            )
        if year_from is not None:
            mask &= self.df["year"] >= year_from
        if year_to is not None:
            mask &= self.df["year"] <= year_to

        candidate_indexes = np.flatnonzero(mask.to_numpy())
        if min_rating is not None:
            first_allowed = np.searchsorted(
                self.sorted_ratings, min_rating, side="left"
            )
            rating_indexes = self.rating_order[first_allowed:]
            candidate_indexes = np.intersect1d(
                candidate_indexes,
                rating_indexes,
                assume_unique=True,
            )
        if not len(candidate_indexes):
            raise ValueError(
                "Не найдено фильмов по выбранным условиям. "
                "Попробуйте ослабить фильтры."
            )

        query = np.hstack(
            [
                genre_vector,
                atmosphere_vector,
                country_vector,
                np.array([[0.5]]),
            ]
        )
        similarities = cosine_similarity(
            query,
            self.X[candidate_indexes],
        )[0]
        candidates = self.df.iloc[candidate_indexes].copy()
        candidates["similarity"] = similarities
        candidates = candidates.sort_values(
            ["similarity", "rating", "popularity"],
            ascending=[False, False, False],
            kind="stable",
        ).head(top_n)
        candidates["description"] = candidates["description"].map(
            self._short_description
        )
        candidates["explanation"] = candidates.apply(
            lambda row: self._explain(row, survey), axis=1
        )
        return candidates[RESULT_COLUMNS].reset_index(drop=True)

    @staticmethod
    def _short_description(value: object) -> str:
        if not isinstance(value, str):
            return ""
        description = " ".join(value.split())
        if len(description) <= 320:
            return description
        return description[:317].rsplit(" ", 1)[0] + "..."

    @staticmethod
    def _explain(row: pd.Series, survey: Mapping[str, object]) -> str:
        reasons: list[str] = []
        genre = survey.get("genre")
        atmosphere = survey.get("atmosphere")
        country = survey.get("country")
        actor = survey.get("actor")
        min_rating = survey.get("min_rating")

        if isinstance(genre, str) and genre.strip():
            reasons.append(f"есть жанр {genre.strip()}")
        if isinstance(atmosphere, str) and atmosphere.strip():
            reasons.append(f"подходит вайб «{atmosphere.strip()}»")
        elif row["atmosphere_str"]:
            reasons.append(f"вайб фильма: {row['atmosphere_str']}")
        if isinstance(country, str) and country.strip():
            reasons.append(f"подходит страна {country.strip()}")
        if isinstance(actor, str) and actor.strip():
            reasons.append(f"в ролях {actor.strip()}")
        if survey.get("year_from") is not None or survey.get("year_to") is not None:
            reasons.append("год выпуска соответствует выбранному диапазону")
        if min_rating is not None and min_rating != "":
            reasons.append(f"IMDb {row['rating']:.1f} не ниже {min_rating}")

        if not reasons:
            reasons.append("высокая совместимость по жанру, вайбу и рейтингу")
        return "Подходит, потому что " + ", ".join(reasons) + "."


if __name__ == "__main__":
    recommender = OwlSimpleRecommender()
    options = recommender.get_options()
    genres = ", ".join(options["genres"])
    atmospheres = ", ".join(options["atmospheres"])
    genre = input(f"Желаемый жанр ({genres}): ").strip() or None
    atmosphere = input(f"Желаемый вайб ({atmospheres}): ").strip() or None
    year_from_input = input("Год выпуска от (необязательно): ").strip()
    year_to_input = input("Год выпуска до (необязательно): ").strip()
    rating_input = input("Минимальный IMDb-рейтинг 0–10 (необязательно): ").strip()
    survey = {
        "genre": genre,
        "atmosphere": atmosphere,
        "year_from": year_from_input or None,
        "year_to": year_to_input or None,
        "min_rating": rating_input or None,
    }
    print(recommender.recommend(survey, top_n=20).to_string(index=False))
