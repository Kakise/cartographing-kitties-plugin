"""Product catalog service."""

from src.models.product import Product, ProductCategory
from src.utils.validators import validate_positive_number


class ProductService:
    """Manages the product catalog."""

    def __init__(self) -> None:
        self._products: dict[int, Product] = {}
        self._next_id: int = 1

    def add_product(
        self,
        name: str,
        price: float,
        category: ProductCategory = ProductCategory.OTHER,
        description: str | None = None,
    ) -> Product:
        """Add a new product to the catalog."""
        if not validate_positive_number(price):
            raise ValueError("Price must be positive")

        product = Product(
            id=self._next_id,
            name=name,
            price=price,
            category=category,
            description=description,
        )
        self._products[product.id] = product
        self._next_id += 1
        return product

    def get_product(self, product_id: int) -> Product | None:
        """Retrieve a product by ID."""
        return self._products.get(product_id)

    def search_products(self, query: str) -> list[Product]:
        """Search products by name or description."""
        query_lower = query.lower()
        results = []
        for product in self._products.values():
            if query_lower in product.name.lower():
                results.append(product)
            elif product.description and query_lower in product.description.lower():
                results.append(product)
        return results

    def get_by_category(self, category: ProductCategory) -> list[Product]:
        """Get all products in a category."""
        return [p for p in self._products.values() if p.category == category]

    def update_stock(self, product_id: int, quantity: int) -> Product:
        """Update stock for a product."""
        product = self.get_product(product_id)
        if product is None:
            raise ValueError(f"Product not found: {product_id}")
        product.restock(quantity)
        return product

    def get_available_products(self) -> list[Product]:
        """Return all in-stock products."""
        return [p for p in self._products.values() if p.is_available()]

    def remove_product(self, product_id: int) -> bool:
        """Remove a product from the catalog."""
        if product_id in self._products:
            del self._products[product_id]
            return True
        return False
