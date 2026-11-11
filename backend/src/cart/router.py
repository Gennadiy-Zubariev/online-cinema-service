from fastapi import APIRouter, status

from src.accounts.dependencies import CurrentUser
from src.cart.service import add_movie_to_cart, remove_movie_from_cart
from src.database.session import DbSession

router = APIRouter(prefix="/cart", tags=["cart"])


@router.put(
    "/items/{movie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def put_cart_item(
    db: DbSession, current_user: CurrentUser, movie_id: int
) -> None:
    """Add a movie to the current user's cart.

    The cart is created on the first added movie.
    Idempotent: adding a movie that is already in the cart changes nothing.
    Returns 404 if the movie does not exist.
    """
    await add_movie_to_cart(db=db, user_id=current_user.id, movie_id=movie_id)


@router.delete(
    "/items/{movie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_cart_item(
    db: DbSession, current_user: CurrentUser, movie_id: int
) -> None:
    """Remove a movie from the current user's cart.

    Idempotent: returns 204 even if the movie is not in the cart.
    """
    await remove_movie_from_cart(db=db, user_id=current_user.id, movie_id=movie_id)
