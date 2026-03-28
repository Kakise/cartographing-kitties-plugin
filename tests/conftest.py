"""Shared test fixtures for Cartograph."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def sample_python_file(tmp_project: Path) -> Path:
    """Create a sample Python file for testing."""
    f = tmp_project / "sample.py"
    f.write_text(
        '''\
import os
from pathlib import Path


class MyClass:
    """A sample class."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}"


def helper_function(x: int) -> int:
    """A helper function."""
    return x + 1


def main():
    obj = MyClass("world")
    print(obj.greet())
    result = helper_function(42)
    print(os.path.join("a", "b"))
'''
    )
    return f


@pytest.fixture
def sample_typescript_file(tmp_project: Path) -> Path:
    """Create a sample TypeScript file for testing."""
    f = tmp_project / "sample.ts"
    f.write_text(
        """\
import { readFile } from "fs/promises";

interface User {
    name: string;
    age: number;
}

type UserID = string;

enum Role {
    Admin = "admin",
    User = "user",
}

class UserService {
    private users: Map<UserID, User> = new Map();

    async getUser(id: UserID): Promise<User | undefined> {
        return this.users.get(id);
    }

    addUser(user: User): void {
        this.users.set(user.name, user);
    }
}

const createUser = (name: string, age: number): User => ({
    name,
    age,
});

export { UserService, createUser };
"""
    )
    return f
