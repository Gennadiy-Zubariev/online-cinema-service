from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
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
SearchText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
Score = Annotated[int, Field(ge=1, le=10)]
CommentText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
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


class MovieDetailResponse(MovieResponse):
    likes: int
    dislikes: int
    rating: float | None
    ratings_count: int


class MovieListItemResponse(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    price: Decimal
    genres: list[NamedEntityResponse]
    poster_url: str | None = None


class MovieListResponse(BaseModel):
    items: list[MovieListItemResponse]
    total: int
    page: int
    page_size: int


class MovieCatalogQuery(BaseModel):
    year_from: MovieYear | None = None
    year_to: MovieYear | None = None
    imdb_min: ImdbRating | None = None
    imdb_max: ImdbRating | None = None
    sort_by: Literal["id", "price", "year", "votes"] = "id"
    order: Literal["asc", "desc"] = "asc"
    search: SearchText | None = None


class MovieReactionRequest(BaseModel):
    is_like: bool


class MovieRatingRequest(BaseModel):
    score: Score


class CommentCreateRequest(BaseModel):
    text: CommentText
    parent_id: int | None = None


class CommentResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    parent_id: int | None
    text: str
    created_at: datetime
    likes: int

    model_config = ConfigDict(from_attributes=True)


class CommentWithRepliesResponse(CommentResponse):
    replies: list[CommentResponse]


class CommentListResponse(BaseModel):
    items: list[CommentWithRepliesResponse]
    total: int
    page: int
    page_size: int
