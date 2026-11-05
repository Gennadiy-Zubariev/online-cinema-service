from typing import Annotated

from pydantic import BaseModel, StringConstraints, ConfigDict

GenreName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class GenreRequest(BaseModel):
    name: GenreName


class GenreResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
