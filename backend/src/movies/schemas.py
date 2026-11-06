from typing import Annotated

from pydantic import BaseModel, StringConstraints, ConfigDict

EntityName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class NamedEntityRequest(BaseModel):
    name: EntityName


class NamedEntityResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
