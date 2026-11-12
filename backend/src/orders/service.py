from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.cart.models import Cart, CartItem
from src.cart.service import list_cart_movies
from src.movies.models import Movie
from src.movies.purchased_service import get_purchased_movie_ids
from src.orders.exceptions import AllMoviesPurchasedError, EmptyCartError
from src.orders.models import Order, OrderItem


async def create_order(
    db: AsyncSession,
    user_id: int,
) -> tuple[Order, list[Movie]]:
    cart_movies = await list_cart_movies(db=db, user_id=user_id)
    if not cart_movies:
        raise EmptyCartError()

    cart_movie_ids = [movie.id for movie in cart_movies]
    purchased_ids = await get_purchased_movie_ids(
        db=db, user_id=user_id, movie_ids=cart_movie_ids
    )
    movies_to_order = [m for m in cart_movies if m.id not in purchased_ids]
    excluded_movies = [m for m in cart_movies if m.id in purchased_ids]
    if not movies_to_order:
        raise AllMoviesPurchasedError()

    order = Order(
        user_id=user_id,
        total_amount=sum(movie.price for movie in movies_to_order),
        items=[
            OrderItem(movie=movie, price_at_order=movie.price)
            for movie in movies_to_order
        ],
    )
    db.add(order)

    cart_id = select(Cart.id).where(Cart.user_id == user_id).scalar_subquery()
    await db.execute(
        delete(CartItem).where(
            CartItem.cart_id == cart_id, CartItem.movie_id.in_(cart_movie_ids)
        )
    )
    await db.commit()
    return order, excluded_movies
