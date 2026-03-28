from src.models.user import User


class UserService:
    def __init__(self):
        self.users: list[User] = []

    def add_user(self, name: str, email: str) -> User:
        user = User(name=name, email=email)
        self.users.append(user)
        return user

    def find_user(self, name: str) -> User | None:
        for user in self.users:
            if user.name == name:
                return user
        return None
