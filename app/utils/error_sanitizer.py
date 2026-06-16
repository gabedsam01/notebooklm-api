from __future__ import annotations

import re

# Nomes de cookies de sessao Google (incluindo variantes __Secure-/__Host-),
# com valor opcional adjacente (`=...` / `: ...`).
_COOKIE_NAMES = (
    r"(?:__Secure-[A-Za-z0-9_-]+|__Host-[A-Za-z0-9_-]+|"
    r"\b(?:SID|HSID|SSID|SAPISID|APISID|OSID|SIDCC|1PSID|3PSID|1PSIDTS|3PSIDTS|PSIDTS)\b)"
    r"(?:\s*[:=]\s*[^\s,;]+)?"
)

# Ordem importa: traceback primeiro (corta o resto), depois paths e tokens.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?is)traceback.*$"), "[redacted]"),
    (re.compile(r"/(?:home|app|tmp|usr|var|root|opt|mnt|Users)/[^\s'\"]*"), "[path]"),
    (re.compile(r"(?i)\bdata/(?:accounts|auth|jobs|artifacts|tmp|run)[^\s'\"]*"), "[path]"),
    (re.compile(r"(?i)[^\s'\"]*storage_state(?:\.json)?[^\s'\"]*"), "[redacted]"),
    (re.compile(r"(?i)[^\s'\"]*chrome-profile[^\s'\"]*"), "[redacted]"),
    (re.compile(r"(?i)bearer\s+[^\s,;]+"), "[redacted]"),
    (re.compile(r"(?i)authorization\b\s*[:=]?\s*[^\s,;]*"), "[redacted]"),
    (
        re.compile(
            r"(?i)\b(?:cookie|cookies|token|tokens|password|passwd|secret|credential|credentials|session)\b"
            r"\s*[:=]?\s*[^\s,;]*"
        ),
        "[redacted]",
    ),
    (re.compile(_COOKIE_NAMES), "[redacted]"),
]

_MAX_LEN = 300


def _scrub(text: str) -> str:
    cleaned = text
    for pattern, repl in _PATTERNS:
        cleaned = pattern.sub(repl, cleaned)
    cleaned = " ".join(cleaned.split())  # colapsa whitespace/newlines
    if len(cleaned) > _MAX_LEN:
        cleaned = cleaned[: _MAX_LEN - 3] + "..."
    return cleaned


def sanitize_exception(exc: Exception) -> str:
    """Mensagem segura derivada da excecao: mantem o nome da classe (util) e
    remove cookies, Authorization/Bearer, storage_state, chrome-profile, paths
    internos e tracebacks."""
    return _scrub(f"{exc.__class__.__name__}: {exc}")
