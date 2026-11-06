from fastapi import APIRouter, Depends, status

from src.accounts.dependencies import get_current_moderator
from src.common.pagination import Pagination
from src.database.session import DbSession
from src.movies.models import Genre
from src.movies.schemas import (
    NamedEntityRequest,
    NamedEntityResponse,
    NamedEntityListResponse,
)
from src.movies.service import (
    create_named,
    list_named,
    get_named,
    update_named,
    delete_named,
)

router = APIRouter(tags=["movies"])


@router.post(
    "/genres",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_genre(data: NamedEntityRequest, db: DbSession) -> Genre:
    """Create a genre (moderator only).

    Leading and trailing whitespace in the name is stripped.
    Returns 409 if a genre with this name already exists.
    """
    return await create_named(db=db, model=Genre, name=data.name)


@router.get(
    "/genres", status_code=status.HTTP_200_OK, response_model=NamedEntityListResponse
)
async def list_genres(db: DbSession, pagination: Pagination) -> NamedEntityListResponse:
    """List genres, ordered by id (public).

    Paginated: `page` starts at 1, `page_size` is 1-100 (default 20).
    A page past the end returns an empty `items` list.
    """
    genres, total = await list_named(
        db=db, model=Genre, page=pagination.page, page_size=pagination.page_size
    )
    return NamedEntityListResponse(
        items=[NamedEntityResponse.model_validate(genre) for genre in genres],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/genres/{genre_id}",
    status_code=status.HTTP_200_OK,
    response_model=NamedEntityResponse,
)
async def get_genre(db: DbSession, genre_id: int) -> Genre:
    """Get a genre by id (public). Returns 404 if it does not exist."""
    return await get_named(db=db, model=Genre, entity_id=genre_id)


@router.patch(
    "/genres/{genre_id}",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_moderator)],
)
async def update_genre(db: DbSession, data: NamedEntityRequest, genre_id: int) -> Genre:
    """Rename a genre (moderator only).

    Returns 404 if the genre does not exist and 409 if another
    genre already has this name.
    """
    return await update_named(db=db, model=Genre, entity_id=genre_id, name=data.name)


@router.delete(
    "/genres/{genre_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_genre(db: DbSession, genre_id: int) -> None:
    """Delete a genre (moderator only).

    The genre is also removed from all movies that had it; the movies
    themselves are kept. Returns 404 if the genre does not exist.
    """
    await delete_named(db=db, model=Genre, entity_id=genre_id)
