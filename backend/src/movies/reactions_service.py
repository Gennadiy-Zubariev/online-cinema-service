from dataclasses import dataclass

from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.movies.exceptions import EntityNotFoundError
from src.movies.models import Movie, MovieReaction, MovieRating


async def set_movie_reaction(
    db: AsyncSession, user_id: int, movie_id: int, is_like: bool
) -> None:
    """Set like (True) or dislike (False); replaces the previous reaction.

    Atomic upsert (ON CONFLICT DO UPDATE). Raises EntityNotFoundError.
    """
    if await db.get(Movie, movie_id) is None:
        raise EntityNotFoundError(Movie.__name__)

    stmt = insert(MovieReaction).values(
        user_id=user_id, movie_id=movie_id, is_like=is_like
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "movie_id"],
        set_={"is_like": is_like},
    )
    await db.execute(stmt)
    await db.commit()


async def delete_movie_reaction(db: AsyncSession, user_id: int, movie_id: int) -> None:
    """Remove the user's reaction; idempotent, no existence checks."""
    await db.execute(
        delete(MovieReaction).where(
            MovieReaction.user_id == user_id, MovieReaction.movie_id == movie_id
        )
    )
    await db.commit()


async def set_movie_rating(
    db: AsyncSession, user_id: int, movie_id: int, score: int
) -> None:
    """Set the user's 1-10 score; replaces the previous one.

    Atomic upsert (ON CONFLICT DO UPDATE). Raises EntityNotFoundError.
    """
    if await db.get(Movie, movie_id) is None:
        raise EntityNotFoundError(Movie.__name__)

    stmt = insert(MovieRating).values(user_id=user_id, movie_id=movie_id, score=score)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "movie_id"],
        set_={"score": score},
    )
    await db.execute(stmt)
    await db.commit()


async def delete_movie_rating(db: AsyncSession, user_id: int, movie_id: int) -> None:
    """Remove the user's score; idempotent, no existence checks."""
    await db.execute(
        delete(MovieRating).where(
            MovieRating.user_id == user_id, MovieRating.movie_id == movie_id
        )
    )
    await db.commit()


@dataclass(frozen=True)
class MovieStats:
    likes: int
    dislikes: int
    rating: float | None
    ratings_count: int


async def get_movie_stats(db: AsyncSession, movie_id: int) -> MovieStats:
    """Return likes, dislikes, average rating (1 decimal) and number of ratings.

    Does not check that the movie exists: the caller loads it first.
    No ratings -> rating is None.
    """
    reactions = (
        await db.execute(
            select(
                func.count().filter(MovieReaction.is_like),
                func.count().filter(MovieReaction.is_like.is_(False)),
            ).where(MovieReaction.movie_id == movie_id)
        )
    ).one()
    ratings = (
        await db.execute(
            select(func.avg(MovieRating.score), func.count()).where(
                MovieRating.movie_id == movie_id
            )
        )
    ).one()
    average = ratings[0]
    return MovieStats(
        likes=reactions[0],
        dislikes=reactions[1],
        rating=round(float(average), 1) if average is not None else None,
        ratings_count=ratings[1],
    )
