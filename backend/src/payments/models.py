import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class PaymentStatusEnum(enum.StrEnum):
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default=PaymentStatusEnum.SUCCESSFUL.value
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    external_payment_id: Mapped[str | None] = mapped_column(String(255), unique=True)
