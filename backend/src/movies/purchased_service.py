from sqlalchemy.ext.asyncio import AsyncSession

from src.movies.models import PurchasedMovie


async def is_movie_purchased(db: AsyncSession, user_id: int, movie_id: int) -> bool:
    return await db.get(PurchasedMovie, (user_id, movie_id)) is not None
