"""API route handlers."""

from src.api.middleware import AuthMiddleware, LoggingMiddleware, Request, Response
from src.models.product import ProductCategory
from src.services.order_service import OrderService
from src.services.product_service import ProductService
from src.services.user_service import UserService
from src.utils.formatters import format_currency
from src.utils.validators import validate_email, validate_required_fields


class UserRoutes:
    """Handles user-related API endpoints."""

    def __init__(
        self, user_service: UserService, auth: AuthMiddleware, logger: LoggingMiddleware
    ) -> None:
        self._user_service = user_service
        self._auth = auth
        self._logger = logger

    def create_user(self, request: Request) -> Response:
        """POST /users -- create a new user."""
        self._logger.log_request(request)
        body = request.body or {}
        missing = validate_required_fields(body, ["name", "email"])
        if missing:
            return Response(status_code=400, body={"error": f"Missing fields: {missing}"})

        if not validate_email(body["email"]):
            return Response(status_code=400, body={"error": "Invalid email"})

        try:
            user = self._user_service.create_user(body["name"], body["email"])
            return Response(status_code=201, body=user.to_dict())
        except ValueError as e:
            return Response(status_code=409, body={"error": str(e)})

    def get_user(self, request: Request, user_id: int) -> Response:
        """GET /users/:id -- retrieve a user."""
        self._logger.log_request(request)
        user = self._user_service.get_user(user_id)
        if user is None:
            return Response(status_code=404, body={"error": "User not found"})
        return Response(status_code=200, body=user.to_dict())

    def list_users(self, request: Request) -> Response:
        """GET /users -- list active users."""
        self._logger.log_request(request)
        users = self._user_service.list_active_users()
        return Response(status_code=200, body=[u.to_dict() for u in users])


class ProductRoutes:
    """Handles product-related API endpoints."""

    def __init__(self, product_service: ProductService, logger: LoggingMiddleware) -> None:
        self._product_service = product_service
        self._logger = logger

    def add_product(self, request: Request) -> Response:
        """POST /products -- add a new product."""
        self._logger.log_request(request)
        body = request.body or {}
        missing = validate_required_fields(body, ["name", "price"])
        if missing:
            return Response(status_code=400, body={"error": f"Missing fields: {missing}"})

        try:
            product = self._product_service.add_product(
                name=body["name"],
                price=body["price"],
                category=ProductCategory(body.get("category", "other")),
                description=body.get("description"),
            )
            return Response(status_code=201, body=product.to_dict())
        except ValueError as e:
            return Response(status_code=400, body={"error": str(e)})

    def search_products(self, request: Request) -> Response:
        """GET /products/search?q=... -- search products."""
        self._logger.log_request(request)
        query = (request.body or {}).get("q", "")
        products = self._product_service.search_products(query)
        return Response(status_code=200, body=[p.to_dict() for p in products])

    def get_product(self, request: Request, product_id: int) -> Response:
        """GET /products/:id -- retrieve a product."""
        self._logger.log_request(request)
        product = self._product_service.get_product(product_id)
        if product is None:
            return Response(status_code=404, body={"error": "Product not found"})
        return Response(status_code=200, body=product.to_dict())


class OrderRoutes:
    """Handles order-related API endpoints."""

    def __init__(
        self, order_service: OrderService, auth: AuthMiddleware, logger: LoggingMiddleware
    ) -> None:
        self._order_service = order_service
        self._auth = auth
        self._logger = logger

    def create_order(self, request: Request) -> Response:
        """POST /orders -- create a new order."""
        self._logger.log_request(request)
        user_id = self._auth.get_user_id(request)
        if user_id is None:
            return Response(status_code=401, body={"error": "Unauthorized"})

        try:
            order = self._order_service.create_order(user_id)
            return Response(status_code=201, body=order.to_dict())
        except ValueError as e:
            return Response(status_code=400, body={"error": str(e)})

    def add_item(self, request: Request, order_id: int) -> Response:
        """POST /orders/:id/items -- add item to order."""
        self._logger.log_request(request)
        body = request.body or {}
        missing = validate_required_fields(body, ["product_id"])
        if missing:
            return Response(status_code=400, body={"error": f"Missing fields: {missing}"})

        try:
            order = self._order_service.add_item_to_order(
                order_id, body["product_id"], body.get("quantity", 1)
            )
            total = format_currency(order.total())
            return Response(status_code=200, body={**order.to_dict(), "formatted_total": total})
        except ValueError as e:
            return Response(status_code=400, body={"error": str(e)})

    def confirm_order(self, request: Request, order_id: int) -> Response:
        """POST /orders/:id/confirm -- confirm an order."""
        self._logger.log_request(request)
        try:
            order = self._order_service.confirm_order(order_id)
            return Response(status_code=200, body=order.to_dict())
        except ValueError as e:
            return Response(status_code=400, body={"error": str(e)})

    def get_user_orders(self, request: Request) -> Response:
        """GET /orders -- get orders for authenticated user."""
        self._logger.log_request(request)
        user_id = self._auth.get_user_id(request)
        if user_id is None:
            return Response(status_code=401, body={"error": "Unauthorized"})
        orders = self._order_service.get_user_orders(user_id)
        return Response(status_code=200, body=[o.to_dict() for o in orders])
