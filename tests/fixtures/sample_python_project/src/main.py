from src.services.user_service import UserService


def main():
    service = UserService()
    service.add_user("Alice", "alice@example.com")
    user = service.find_user("Alice")
    if user:
        print(user.display_name())


if __name__ == "__main__":
    main()
