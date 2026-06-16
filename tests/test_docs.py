"""Onda 8 - testes de documentacao/release (sem segredos reais)."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = [
    ROOT / "README.md",
    ROOT / "SECURITY.md",
    ROOT / "CHANGELOG.md",
    ROOT / "docs" / "upgrade-0.2.md",
    ROOT / "docs" / "smoke-test.md",
    ROOT / ".env.example",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_required_docs_exist() -> None:
    for path in [
        ROOT / "SECURITY.md",
        ROOT / "CHANGELOG.md",
        ROOT / "docs" / "upgrade-0.2.md",
        ROOT / "docs" / "smoke-test.md",
    ]:
        assert path.exists(), f"faltou doc obrigatorio: {path.name}"


def test_env_example_has_security_settings() -> None:
    env = _read(ROOT / ".env.example")
    for key in (
        "API_AUTH_TOKEN",
        "ALLOW_INSECURE_NO_AUTH",
        "CORS_ALLOW_ORIGINS",
        "CORS_ALLOW_METHODS",
        "CORS_ALLOW_HEADERS",
        "CORS_ALLOW_CREDENTIALS",
    ):
        assert key in env, f"faltou {key} no .env.example"


def test_env_example_has_no_real_token() -> None:
    env = _read(ROOT / ".env.example")
    # token deve estar vazio (placeholder), nunca um valor real
    assert re.search(r'API_AUTH_TOKEN\s*=\s*""', env), "API_AUTH_TOKEN deve estar vazio no .env.example"


def test_pyproject_version_is_0_2_0() -> None:
    data = tomllib.loads(_read(ROOT / "pyproject.toml"))
    assert data["project"]["version"] == "0.2.0"


def test_readme_documents_account_field_removal() -> None:
    readme = _read(ROOT / "README.md")
    # storage_state_path/chrome_profile_path so podem aparecer no contexto de remocao
    assert "storage_state_path" in readme and "chrome_profile_path" in readme
    assert "removeu" in readme or "removido" in readme


def test_docs_have_no_real_secrets() -> None:
    bearer = re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")
    cookie_value = re.compile(
        r"(?:\bSID|__Secure-1PSID|__Secure-1PSIDTS|SAPISID|APISID)\s*=\s*[A-Za-z0-9._/+-]{8,}"
    )
    for path in DOCS:
        if not path.exists():
            continue
        text = _read(path)
        assert not bearer.search(text), f"possivel token Bearer real em {path.name}"
        assert not cookie_value.search(text), f"possivel cookie com valor em {path.name}"
