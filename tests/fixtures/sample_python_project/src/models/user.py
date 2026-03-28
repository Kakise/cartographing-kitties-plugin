from dataclasses import dataclass


@dataclass
class User:
    name: str
    email: str

    def display_name(self) -> str:
        return self.name.title()
