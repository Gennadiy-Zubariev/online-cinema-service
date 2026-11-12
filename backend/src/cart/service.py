from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cart.exceptions import MovieAlreadyPurchasedError
from src.cart.models import Cart, CartItem
from src.movies.exceptions import EntityNotFoundError
from src.movies.models import Movie
from src.movies.purchased_service import is_movie_purchased


async def _get_or_create_cart(
    db: AsyncSession,
    user_id: int,
) -> Cart:
    await db.execute(
        insert(Cart)
        .values(user_id=user_id)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    result = await db.execute(select(Cart).where(Cart.user_id == user_id))
    return result.scalar_one()


async def add_movie_to_cart(
    db: AsyncSession,
    user_id: int,
    movie_id: int,
) -> None:
    if await db.get(Movie, movie_id) is None:
        raise EntityNotFoundError(Movie.__name__)
    if await is_movie_purchased(db=db, user_id=user_id, movie_id=movie_id):
        raise MovieAlreadyPurchasedError()
    cart = await _get_or_create_cart(db=db, user_id=user_id)
    await db.execute(
        insert(CartItem)
        .values(cart_id=cart.id, movie_id=movie_id)
        .on_conflict_do_nothing(index_elements=["cart_id", "movie_id"])
    )
    await db.commit()


async def remove_movie_from_cart(db: AsyncSession, user_id: int, movie_id: int) -> None:
    cart_id = select(Cart.id).where(Cart.user_id == user_id).scalar_subquery()
    await db.execute(
        delete(CartItem).where(
            CartItem.cart_id == cart_id, CartItem.movie_id == movie_id
        )
    )
    await db.commit()


async def list_cart_movies(db: AsyncSession, user_id: int) -> list[Movie]:
    result = await db.scalars(
        select(Movie)
        .join(CartItem, CartItem.movie_id == Movie.id)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(Cart.user_id == user_id)
        .options(selectinload(Movie.genres))
        .order_by(CartItem.id)
    )
    return list(result.all())


async def clear_cart(db: AsyncSession, user_id: int) -> None:
    cart_id = select(Cart.id).where(Cart.user_id == user_id).scalar_subquery()
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart_id))
    await db.commit()
