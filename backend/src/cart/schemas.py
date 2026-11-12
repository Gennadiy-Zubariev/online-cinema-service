from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.movies.schemas import NamedEntityResponse


class CartMovieResponse(BaseModel):
    id: int
    name: str
    year: int
    price: Decimal
    genres: list[NamedEntityResponse]

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    items: list[CartMovieResponse]
