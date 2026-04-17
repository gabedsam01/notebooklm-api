from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    hash_builder = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(8192), b""):
            hash_builder.update(chunk)
    return hash_builder.hexdigest()
