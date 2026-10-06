from collections.abc import Mapping
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_PATH = "database/movies_for_training.csv"
RESULT_COLUMNS = [
    "movie_name", "year", "genres_str", "rating", "atmosphere_str", "similarity"
]


class OwlSimpleRecommender:
    def __init__(self, data_path: str | Path | None = None):
        if data_path is None:
            data_path = Path(__file__).resolve().parent / DATA_PATH

        df = pd.read_csv(data_path)
        required_columns = {
            "movie_name", "year", "genres_str", "rating", "atmosphere_str"
        }
        missing_columns = required_columns.difference(df.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"В CSV отсутствуют обязательные столбцы: {missing}")

        df = df.fillna({
            "genres_str": "", "atmosphere_str": "", "era": "unknown",
            "rating": 0, "popularity": 0,
        })
        df["genres_list"] = df["genres_str"].apply(
            lambda value: [tag.strip() for tag in value.split("|") if tag.strip()]
        )
        df["atmosphere_list"] = df["atmosphere_str"].apply(
            lambda value: [tag.strip() for tag in value.split("|") if tag.strip()]
        )
        self.df = df.reset_index(drop=True)

        # Каждый теговый признак -> свой 0/1-вектор через MultiLabelBinarizer
        self.genre_mlb = MultiLabelBinarizer()
        genre_matrix = self.genre_mlb.fit_transform(self.df["genres_list"])

        self.atmo_mlb = MultiLabelBinarizer()
        atmo_matrix = self.atmo_mlb.fit_transform(self.df["atmosphere_list"])

        # Рейтинг нормализуем в 0..1, чтобы он был в той же шкале, что 0/1-теги
        rating_col = (self.df["rating"] / 10.0).to_numpy().reshape(-1, 1)

        # Просто склеиваем все векторы горизонтально в одну матрицу признаков
        self.X = np.hstack([genre_matrix, atmo_matrix, rating_col])

    @staticmethod
    def _encode_preference(value: str | None, binarizer: MultiLabelBinarizer, field: str):
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Значение «{field}» должно быть строкой.")
        if value is None or not value.strip():
            return np.zeros((1, len(binarizer.classes_)))

        normalized_value = value.strip().casefold()
        matching_tags = {
            tag.casefold(): tag for tag in binarizer.classes_
        }
        if normalized_value not in matching_tags:
            choices = ", ".join(binarizer.classes_)
            raise ValueError(
                f"Неизвестное значение «{value}» для поля «{field}». "
                f"Допустимые значения: {choices}"
            )

        return binarizer.transform([[matching_tags[normalized_value]]])

    def recommend(
        self, survey: Mapping[str, str | None], top_n: int = 5
    ) -> pd.DataFrame:
        if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n <= 0:
            raise ValueError("top_n должен быть положительным целым числом.")

        genre_vec = self._encode_preference(
            survey.get("genre"), self.genre_mlb, "жанр"
        )
        atmo_vec = self._encode_preference(
            survey.get("atmosphere"), self.atmo_mlb, "атмосфера"
        )

        rating_vec = np.array([[1.0]])  # хотим максимально высокий рейтинг

        query = np.hstack([genre_vec, atmo_vec, rating_vec])

        # Одна строчка - вся "магия": похожесть анкеты на каждый фильм
        sims = cosine_similarity(query, self.X)[0]

        result = self.df.assign(similarity=sims).sort_values(
            "similarity", ascending=False, kind="stable"
        ).head(top_n)
        return result[RESULT_COLUMNS].reset_index(drop=True)


if __name__ == "__main__":
    owl = OwlSimpleRecommender()
    
    genres = ["Action", "Adventure", "Animation", "Biography", "Comedy", "Crime",
    "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Musical",
    "Mystery", "Romance", "Sci-Fi", "Sport", "Thriller", "War", "Western"]

    genre = input(f'какой фильм вы хотите посмотреть? (жанр): {", ".join(genres)}: ')

    atmospheres = ["эмоциональное", "мрачное", "напряжённое", "весёлое", "лёгкое",
    "романтическое", "адреналиновое", "пугающее", "семейное",
    "приключенческое", "уютное", "загадочное", "детективное",
    "волшебное", "военное", "футуристичное", "мотивирующее",
    "вдохновляющее", "вдумчивое", "тяжёлое", "мистическое",
    "основано на реальных событиях", "атмосферное", "новогоднее",
    "хэллоуинское"]

    atmosphere = input(f'какая атмосфера вам нравится? (атмосфера): {", ".join(atmospheres)}: ')
    survey = {"genre": genre, "atmosphere": atmosphere}
    print(owl.recommend(survey, top_n=5).to_string(index=False))

    