"""Order domain model."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.models.product import Product
from src.models.user import User


class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass
class OrderItem:
    product: Product
    quantity: int

    def subtotal(self) -> float:
        return round(self.product.price * self.quantity, 2)


@dataclass
class Order:
    id: int
    user: User
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    notes: str | None = None

    def total(self) -> float:
        return round(sum(item.subtotal() for item in self.items), 2)

    def add_item(self, product: Product, quantity: int = 1) -> None:
        for item in self.items:
            if item.product.id == product.id:
                item.quantity += quantity
                return
        self.items.append(OrderItem(product=product, quantity=quantity))

    def remove_item(self, product_id: int) -> bool:
        for i, item in enumerate(self.items):
            if item.product.id == product_id:
                self.items.pop(i)
                return True
        return False

    def confirm(self) -> None:
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot confirm order with status {self.status}")
        self.status = OrderStatus.CONFIRMED

    def cancel(self) -> None:
        if self.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
            raise ValueError("Cannot cancel shipped or delivered order")
        self.status = OrderStatus.CANCELLED

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user": self.user.to_dict(),
            "items": [
                {"product": i.product.to_dict(), "quantity": i.quantity, "subtotal": i.subtotal()}
                for i in self.items
            ],
            "total": self.total(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }
