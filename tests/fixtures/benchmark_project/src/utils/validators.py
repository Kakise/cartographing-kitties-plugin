"""Input validation utilities."""

import re
from typing import Any


def validate_email(email: str) -> bool:
    """Validate an email address format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate a phone number (US format)."""
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(r"^\+?1?\d{10}$", cleaned))


def validate_positive_number(value: Any) -> bool:
    """Check that value is a positive number."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def validate_required_fields(data: dict, required: list[str]) -> list[str]:
    """Return list of missing required fields."""
    missing = []
    for field_name in required:
        if field_name not in data or data[field_name] is None:
            missing.append(field_name)
    return missing


def sanitize_string(value: str, max_length: int | None = None) -> str:
    """Sanitize a string by stripping whitespace and optionally truncating."""
    result = value.strip()
    if max_length is not None and len(result) > max_length:
        result = result[:max_length]
    return result
