"""User management service."""

from src.models.user import Address, User
from src.services.notification_service import NotificationService
from src.utils.validators import validate_email


class UserService:
    """Manages user creation, lookup, and updates."""

    def __init__(self, notification_service: NotificationService | None = None) -> None:
        self._users: dict[int, User] = {}
        self._next_id: int = 1
        self._notifications = notification_service or NotificationService()

    def create_user(self, name: str, email: str) -> User:
        """Create a new user after validating input."""
        if not validate_email(email):
            raise ValueError(f"Invalid email: {email}")
        if self.find_by_email(email) is not None:
            raise ValueError(f"Email already in use: {email}")

        user = User(id=self._next_id, name=name, email=email)
        self._users[user.id] = user
        self._next_id += 1

        self._notifications.send(user, "Welcome!", f"Welcome to the platform, {name}!")
        return user

    def get_user(self, user_id: int) -> User | None:
        """Retrieve a user by ID."""
        return self._users.get(user_id)

    def find_by_email(self, email: str) -> User | None:
        """Find a user by their email address."""
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    def find_by_name(self, name: str) -> list[User]:
        """Search users whose name contains the given string."""
        name_lower = name.lower()
        return [u for u in self._users.values() if name_lower in u.name.lower()]

    def update_address(self, user_id: int, address: Address) -> User:
        """Update a user's address."""
        user = self.get_user(user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        user.address = address
        return user

    def deactivate_user(self, user_id: int) -> None:
        """Deactivate a user account."""
        user = self.get_user(user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        user.deactivate()
        self._notifications.send(user, "Account Deactivated", "Your account has been deactivated.")

    def list_active_users(self) -> list[User]:
        """Return all active users."""
        return [u for u in self._users.values() if u.is_active]

    def count(self) -> int:
        """Return total number of users."""
        return len(self._users)
