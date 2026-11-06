from fastapi import APIRouter, Depends, status

from src.accounts.dependencies import get_current_moderator
from src.database.session import DbSession
from src.movies.models import Genre
from src.movies.schemas import NamedEntityRequest, NamedEntityResponse
from src.movies.service import create_named

router = APIRouter(tags=["movies"])


@router.post(
    "/genres",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_genre_route(data: NamedEntityRequest, db: DbSession) -> Genre:
    """Create a genre (moderator only). Returns 409 if the name is taken."""
    return await create_named(db=db, model=Genre, name=data.name)
