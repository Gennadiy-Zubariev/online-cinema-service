from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.movies.schemas import NamedEntityResponse
from src.orders.models import OrderStatusEnum


class OrderItemResponse(BaseModel):
    id: int
    movie: NamedEntityResponse
    price_at_order: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    created_at: datetime
    status: OrderStatusEnum
    total_amount: Decimal | None
    items: list[OrderItemResponse]

    model_config = ConfigDict(from_attributes=True)


class OrderCreateResponse(OrderResponse):
    excluded_movies: list[NamedEntityResponse]
