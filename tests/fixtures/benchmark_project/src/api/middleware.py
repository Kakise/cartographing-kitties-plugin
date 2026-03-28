"""API middleware for request processing."""

import time
from dataclasses import dataclass, field
from typing import Any

from src.config.settings import AppConfig


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Response:
    status_code: int
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)


class AuthMiddleware:
    """Validates authentication tokens on incoming requests."""

    def __init__(self, secret_key: str) -> None:
        self._secret_key = secret_key

    def authenticate(self, request: Request) -> bool:
        """Check if request has a valid auth token."""
        token = request.headers.get("Authorization", "")
        if not token.startswith("Bearer "):
            return False
        return len(token) > 7

    def get_user_id(self, request: Request) -> int | None:
        """Extract user ID from the auth token."""
        token = request.headers.get("Authorization", "")
        if not self.authenticate(request):
            return None
        try:
            return int(token.split(".")[-1])
        except (ValueError, IndexError):
            return None


class CorsMiddleware:
    """Handles CORS headers for cross-origin requests."""

    def __init__(self, config: AppConfig) -> None:
        self._allowed_origins = config.get_cors_origins()

    def process_request(self, request: Request) -> Response | None:
        """Handle preflight OPTIONS requests."""
        if request.method == "OPTIONS":
            return Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                },
            )
        return None

    def add_cors_headers(self, response: Response, origin: str) -> Response:
        """Add CORS headers to a response."""
        if origin in self._allowed_origins or "*" in self._allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
        return response


class LoggingMiddleware:
    """Logs request and response details."""

    def __init__(self) -> None:
        self._logs: list[dict[str, Any]] = []

    def log_request(self, request: Request) -> None:
        """Log an incoming request."""
        self._logs.append(
            {
                "type": "request",
                "method": request.method,
                "path": request.path,
                "timestamp": request.timestamp,
            }
        )

    def log_response(self, request: Request, response: Response, duration_ms: float) -> None:
        """Log a completed response."""
        self._logs.append(
            {
                "type": "response",
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }
        )

    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent logs."""
        return self._logs[-limit:]
