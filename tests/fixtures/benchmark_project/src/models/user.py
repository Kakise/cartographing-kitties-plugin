"""User domain model."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Address:
    street: str
    city: str
    state: str
    zip_code: str

    def format_full(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}"


@dataclass
class User:
    id: int
    name: str
    email: str
    address: Address | None = None
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

    def display_name(self) -> str:
        return self.name.title()

    def validate_email(self) -> bool:
        return "@" in self.email and "." in self.email.split("@")[1]

    def deactivate(self) -> None:
        self.is_active = False

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }
        if self.address:
            result["address"] = self.address.format_full()
        return result
