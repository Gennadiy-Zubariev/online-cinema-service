from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints, ConfigDict, Field

EntityName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
MovieDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


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
    year: int = Field(ge=1888)
    time: int = Field(gt=0)
    imdb: float = Field(ge=0, le=10)
    votes: int = Field(ge=0)
    meta_score: float | None = Field(default=None, ge=0, le=100)
    gross: float | None = Field(default=None, ge=0)
    description: MovieDescription
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    certification_id: int
    genre_ids: set[int] = set()
    director_ids: set[int] = set()
    star_ids: set[int] = set()


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

    model_config = ConfigDict(from_attributes=True)
