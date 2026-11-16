"""File hashing, used to detect duplicate uploads."""

import hashlib
from pathlib import Path

_READ_BLOCK_SIZE = 1024 * 1024  # 1 MB


def sha256_file(path: Path) -> str:
    """Hash a file in blocks so large files don't have to fit in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(_READ_BLOCK_SIZE):
            digest.update(block)
    return digest.hexdigest()
