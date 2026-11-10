from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.movies.exceptions import EntityNotFoundError
from src.movies.models import FavoriteMovie, Movie
from src.movies.movies_service import list_catalog_movies
from src.movies.schemas import MovieCatalogQuery


async def add_favorite_movie(db: AsyncSession, user_id: int, movie_id: int) -> None:
    if await db.get(Movie, movie_id) is None:
        raise EntityNotFoundError(Movie.__name__)

    stmt = insert(FavoriteMovie).values(user_id=user_id, movie_id=movie_id)
    stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "movie_id"])
    await db.execute(stmt)
    await db.commit()


async def remove_favorite_movie(db: AsyncSession, user_id: int, movie_id: int) -> None:
    await db.execute(
        delete(FavoriteMovie).where(
            FavoriteMovie.user_id == user_id, FavoriteMovie.movie_id == movie_id
        )
    )
    await db.commit()


async def list_favorite_movies(
    db: AsyncSession,
    user_id: int,
    params: MovieCatalogQuery,
    page: int,
    page_size: int,
) -> tuple[list[Movie], int]:
    stmt = (
        select(Movie)
        .join(FavoriteMovie, FavoriteMovie.movie_id == Movie.id)
        .where(FavoriteMovie.user_id == user_id)
    )
    return await list_catalog_movies(
        db=db, stmt=stmt, params=params, page=page, page_size=page_size
    )
