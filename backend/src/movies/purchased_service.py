from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.movies.models import PurchasedMovie, Movie
from src.movies.movies_service import list_catalog_movies
from src.movies.schemas import MovieCatalogQuery


async def is_movie_purchased(db: AsyncSession, user_id: int, movie_id: int) -> bool:
    return await db.get(PurchasedMovie, (user_id, movie_id)) is not None


async def get_purchased_movie_ids(
    db: AsyncSession, user_id: int, movie_ids: list[int]
) -> set[int]:
    result = await db.scalars(
        select(PurchasedMovie.movie_id).where(
            PurchasedMovie.user_id == user_id,
            PurchasedMovie.movie_id.in_(movie_ids),
        )
    )
    return set(result.all())


async def list_purchased_movies(
    db: AsyncSession,
    user_id: int,
    params: MovieCatalogQuery,
    page: int,
    page_size: int,
) -> tuple[list[Movie], int]:
    stmt = (
        select(Movie)
        .join(PurchasedMovie, PurchasedMovie.movie_id == Movie.id)
        .where(PurchasedMovie.user_id == user_id)
    )
    return await list_catalog_movies(
        db=db, stmt=stmt, params=params, page=page, page_size=page_size
    )
