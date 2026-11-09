from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints, ConfigDict, Field, field_validator

EntityName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
MovieDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
MovieYear = Annotated[int, Field(ge=1888)]
MovieTime = Annotated[int, Field(gt=0)]
ImdbRating = Annotated[float, Field(ge=0, le=10)]
Votes = Annotated[int, Field(ge=0)]
MetaScore = Annotated[float, Field(ge=0, le=100)]
Gross = Annotated[float, Field(ge=0)]
Price = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class NamedEntityRequest(BaseModel):
    name: EntityName


class NamedEntityResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class NamedEntityListResponse(BaseModel):
    items: list[NamedEntityResponse]
    total: int
    page: int
    page_size: int


class MovieCreateRequest(BaseModel):
    name: EntityName
    year: MovieYear
    time: MovieTime
    imdb: ImdbRating
    votes: Votes
    meta_score: MetaScore | None = None
    gross: Gross | None = None
    description: MovieDescription
    price: Price
    certification_id: int
    genre_ids: set[int] = set()
    director_ids: set[int] = set()
    star_ids: set[int] = set()


class MovieUpdateRequest(BaseModel):
    name: EntityName | None = None
    year: MovieYear | None = None
    time: MovieTime | None = None
    imdb: ImdbRating | None = None
    votes: Votes | None = None
    meta_score: MetaScore | None = None
    gross: Gross | None = None
    description: MovieDescription | None = None
    price: Price | None = None
    certification_id: int | None = None
    genre_ids: set[int] | None = None
    director_ids: set[int] | None = None
    star_ids: set[int] | None = None

    @field_validator(
        "name",
        "year",
        "time",
        "imdb",
        "votes",
        "description",
        "price",
        "certification_id",
        "genre_ids",
        "director_ids",
        "star_ids",
    )
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class MovieResponse(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float | None
    gross: float | None
    description: str
    price: Decimal
    certification: NamedEntityResponse
    genres: list[NamedEntityResponse]
    directors: list[NamedEntityResponse]
    stars: list[NamedEntityResponse]
    poster_url: str | None = None

    model_config = ConfigDict(from_attributes=True)
