from dataclasses import dataclass
from typing import Annotated

from fastapi import Query, Depends


@dataclass
class PaginationParams:
    """Query parameters page (from 1) and page_size (1-100) for list endpoints.

    Used only in routers (via Pagination); services take plain ints.
    """

    page: Annotated[int, Query(ge=1)] = 1
    page_size: Annotated[int, Query(ge=1, le=100)] = 20


Pagination = Annotated[PaginationParams, Depends()]
