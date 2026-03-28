"""Formatting utility functions."""

from datetime import datetime


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format a numeric amount as currency string."""
    symbols = {"USD": "$", "EUR": "\u20ac", "GBP": "\u00a3"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"


def format_date(dt: datetime, fmt: str | None = None) -> str:
    """Format a datetime with optional format string."""
    if fmt is None:
        fmt = "%Y-%m-%d %H:%M:%S"
    return dt.strftime(fmt)


def format_name(first: str, last: str) -> str:
    """Format a full name from parts."""
    return f"{first.strip().title()} {last.strip().title()}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to max_length, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def format_file_size(size_bytes: int) -> str:
    """Format byte size as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
