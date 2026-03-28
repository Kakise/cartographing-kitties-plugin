"""Product domain model."""

from dataclasses import dataclass
from enum import Enum


class ProductCategory(Enum):
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    FOOD = "food"
    BOOKS = "books"
    OTHER = "other"


@dataclass
class Product:
    id: int
    name: str
    price: float
    category: ProductCategory = ProductCategory.OTHER
    description: str | None = None
    stock_count: int = 0

    def is_available(self) -> bool:
        return self.stock_count > 0

    def apply_discount(self, percentage: float) -> float:
        if not 0 <= percentage <= 100:
            raise ValueError("Discount must be between 0 and 100")
        discount = self.price * (percentage / 100)
        return round(self.price - discount, 2)

    def restock(self, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("Cannot restock negative quantity")
        self.stock_count += quantity

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "category": self.category.value,
            "description": self.description,
            "stock_count": self.stock_count,
        }
