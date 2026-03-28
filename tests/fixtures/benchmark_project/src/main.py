"""Application entry point."""

from src.api.middleware import AuthMiddleware, CorsMiddleware, LoggingMiddleware
from src.api.routes import OrderRoutes, ProductRoutes, UserRoutes
from src.config.settings import load_config
from src.services.notification_service import NotificationService
from src.services.order_service import OrderService
from src.services.product_service import ProductService
from src.services.user_service import UserService


def create_app(env: str = "development") -> dict:
    """Bootstrap the application with all dependencies wired up."""
    config = load_config(env)

    # Services
    notification_service = NotificationService()
    user_service = UserService(notification_service=notification_service)
    product_service = ProductService()
    order_service = OrderService(
        user_service=user_service,
        product_service=product_service,
        notification_service=notification_service,
    )

    # Middleware
    auth = AuthMiddleware(secret_key=config.secret_key or "dev-secret")
    cors = CorsMiddleware(config)
    logger = LoggingMiddleware()

    # Routes
    user_routes = UserRoutes(user_service, auth, logger)
    product_routes = ProductRoutes(product_service, logger)
    order_routes = OrderRoutes(order_service, auth, logger)

    return {
        "config": config,
        "services": {
            "users": user_service,
            "products": product_service,
            "orders": order_service,
            "notifications": notification_service,
        },
        "routes": {
            "users": user_routes,
            "products": product_routes,
            "orders": order_routes,
        },
        "middleware": {
            "auth": auth,
            "cors": cors,
            "logger": logger,
        },
    }


def main() -> None:
    """Run the application."""
    app = create_app()
    config = app["config"]
    print(f"Starting {config.app_name} v{config.version}")
    print(f"Debug mode: {config.debug}")

    # Demo: create a user
    users = app["services"]["users"]
    user = users.create_user("Alice", "alice@example.com")
    print(f"Created user: {user.display_name()}")


if __name__ == "__main__":
    main()
