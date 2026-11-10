from dataclasses import dataclass
from typing import Annotated

from fastapi import Query, Depends


@dataclass
class PaginationParams:
    page: Annotated[int, Query(ge=1)] = 1
    page_size: Annotated[int, Query(ge=1, le=100)] = 20


Pagination = Annotated[PaginationParams, Depends()]
