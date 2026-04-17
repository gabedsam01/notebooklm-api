from __future__ import annotations

import re


_SENSITIVE_PATTERN = re.compile(
    r"(?i)(cookie|token|authorization|password|session)[^\n\r]{0,120}"
)


def sanitize_exception(exc: Exception) -> str:
    raw = f"{exc.__class__.__name__}: {exc}"
    cleaned = _SENSITIVE_PATTERN.sub("[redacted]", raw)
    if len(cleaned) > 400:
        return cleaned[:397] + "..."
    return cleaned
