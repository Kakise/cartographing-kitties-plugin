"""Cartograph indexing -- file discovery, change detection, and structural indexing."""

from cartograph.indexing.discovery import (
    ChangedFiles,
    compute_file_hash,
    detect_changes,
    discover_files,
)
from cartograph.indexing.indexer import Indexer, IndexStats

__all__ = [
    "ChangedFiles",
    "IndexStats",
    "Indexer",
    "compute_file_hash",
    "detect_changes",
    "discover_files",
]
