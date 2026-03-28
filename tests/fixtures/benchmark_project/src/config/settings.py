"""Application configuration."""

from dataclasses import dataclass, field


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    name: str = "app_db"
    user: str = "admin"
    password: str = ""

    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class CacheConfig:
    enabled: bool = True
    ttl_seconds: int = 300
    max_size: int = 1000


@dataclass
class AppConfig:
    app_name: str = "MyApp"
    debug: bool = False
    version: str = "1.0.0"
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    secret_key: str | None = None
    allowed_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])

    def is_production(self) -> bool:
        return not self.debug

    def get_cors_origins(self) -> list[str]:
        if self.debug:
            return ["*"]
        return self.allowed_origins


def load_config(env: str = "development") -> AppConfig:
    """Load configuration based on environment."""
    if env == "production":
        return AppConfig(
            debug=False,
            secret_key="prod-secret",
            database=DatabaseConfig(host="db.prod.example.com"),
        )
    elif env == "testing":
        return AppConfig(
            debug=True,
            database=DatabaseConfig(name="test_db"),
        )
    return AppConfig(debug=True)
