from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.movies.exceptions import EntityNotFoundError
from src.movies.models import FavoriteMovie, Movie


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
