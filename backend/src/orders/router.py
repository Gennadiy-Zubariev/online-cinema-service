from fastapi import APIRouter, status

from src.accounts.dependencies import CurrentUser
from src.common.pagination import Pagination
from src.database.session import DbSession
from src.movies.schemas import NamedEntityResponse
from src.orders.schemas import (
    OrderCreateResponse,
    OrderItemResponse,
    OrderListResponse,
    OrderResponse,
)
from src.orders.service import create_order, list_orders

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=OrderCreateResponse
)
async def add_order(db: DbSession, current_user: CurrentUser) -> OrderCreateResponse:
    """Create an order from the current user's cart.

    Already purchased movies are excluded and listed in `excluded_movies`.
    Ordered and excluded movies are removed from the cart.
    Returns 400 if the cart is empty or all its movies are already purchased.
    """
    order, excluded_movies = await create_order(db=db, user_id=current_user.id)
    return OrderCreateResponse(
        id=order.id,
        created_at=order.created_at,
        status=order.status,
        total_amount=order.total_amount,
        items=[OrderItemResponse.model_validate(item) for item in order.items],
        excluded_movies=[
            NamedEntityResponse.model_validate(movie) for movie in excluded_movies
        ],
    )


@router.get("", status_code=status.HTTP_200_OK, response_model=OrderListResponse)
async def get_orders_list(
    db: DbSession, current_user: CurrentUser, pagination: Pagination
) -> OrderListResponse:
    """List the current user's orders, newest first.

    Each order includes its items (movie and price at order time), total and status.
    """
    orders, total = await list_orders(
        db=db,
        user_id=current_user.id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return OrderListResponse(
        items=[OrderResponse.model_validate(order) for order in orders],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
