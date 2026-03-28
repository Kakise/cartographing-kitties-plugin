"""Order management service."""

from src.models.order import Order, OrderStatus
from src.services.notification_service import NotificationService
from src.services.product_service import ProductService
from src.services.user_service import UserService
from src.utils.formatters import format_currency


class OrderService:
    """Manages order creation, updates, and queries."""

    def __init__(
        self,
        user_service: UserService,
        product_service: ProductService,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._orders: dict[int, Order] = {}
        self._next_id: int = 1
        self._user_service = user_service
        self._product_service = product_service
        self._notifications = notification_service or NotificationService()

    def create_order(self, user_id: int) -> Order:
        """Create an empty order for a user."""
        user = self._user_service.get_user(user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")

        order = Order(id=self._next_id, user=user)
        self._orders[order.id] = order
        self._next_id += 1
        return order

    def add_item_to_order(self, order_id: int, product_id: int, quantity: int = 1) -> Order:
        """Add a product to an existing order."""
        order = self.get_order(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")

        product = self._product_service.get_product(product_id)
        if product is None:
            raise ValueError(f"Product not found: {product_id}")

        if not product.is_available():
            raise ValueError(f"Product out of stock: {product.name}")

        order.add_item(product, quantity)
        return order

    def get_order(self, order_id: int) -> Order | None:
        """Retrieve an order by ID."""
        return self._orders.get(order_id)

    def confirm_order(self, order_id: int) -> Order:
        """Confirm a pending order."""
        order = self.get_order(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")

        order.confirm()
        total = format_currency(order.total())
        self._notifications.send(
            order.user,
            "Order Confirmed",
            f"Your order #{order.id} for {total} has been confirmed.",
        )
        return order

    def cancel_order(self, order_id: int) -> Order:
        """Cancel an order."""
        order = self.get_order(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")

        order.cancel()
        self._notifications.send(
            order.user,
            "Order Cancelled",
            f"Your order #{order.id} has been cancelled.",
        )
        return order

    def get_user_orders(self, user_id: int) -> list[Order]:
        """Get all orders for a user."""
        return [o for o in self._orders.values() if o.user.id == user_id]

    def get_pending_orders(self) -> list[Order]:
        """Get all pending orders."""
        return [o for o in self._orders.values() if o.status == OrderStatus.PENDING]

    def get_order_summary(self, order_id: int) -> dict:
        """Get a formatted summary of an order."""
        order = self.get_order(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")
        return order.to_dict()
