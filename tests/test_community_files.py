"""Community health files: existência, licença MIT e ausência de segredos reais."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GH = ROOT / ".github"

COMMUNITY = [
    ROOT / "LICENSE",
    ROOT / "CONTRIBUTING.md",
    ROOT / "CODE_OF_CONDUCT.md",
    ROOT / "SUPPORT.md",
    ROOT / "SECURITY.md",
    GH / "PULL_REQUEST_TEMPLATE.md",
    GH / "ISSUE_TEMPLATE" / "bug_report.md",
    GH / "ISSUE_TEMPLATE" / "feature_request.md",
    GH / "ISSUE_TEMPLATE" / "security_report.md",
    GH / "ISSUE_TEMPLATE" / "config.yml",
    GH / "dependabot.yml",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_license_exists_and_is_mit() -> None:
    lic = _read(ROOT / "LICENSE")
    assert "MIT License" in lic
    assert "Gabriel Sampaio" in lic


def test_readme_mentions_license() -> None:
    readme = _read(ROOT / "README.md")
    assert "LICENSE" in readme and "MIT" in readme


def test_pyproject_declares_mit() -> None:
    data = tomllib.loads(_read(ROOT / "pyproject.toml"))
    assert "MIT" in str(data["project"].get("license"))


def test_community_files_exist() -> None:
    for path in COMMUNITY:
        assert path.exists(), f"faltou: {path.relative_to(ROOT)}"


def test_issue_templates_have_frontmatter() -> None:
    for name in ("bug_report.md", "feature_request.md", "security_report.md"):
        text = _read(GH / "ISSUE_TEMPLATE" / name)
        assert text.startswith("---"), f"{name} sem frontmatter"
        assert "name:" in text and "about:" in text


def test_dependabot_blocks_notebooklm_py_0_8() -> None:
    dep = _read(GH / "dependabot.yml")
    assert "notebooklm-py" in dep
    assert ">=0.8" in dep  # 0.8 nao deve subir automaticamente (error contract)


def test_no_real_secrets_in_new_files() -> None:
    bearer = re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")
    cookie_value = re.compile(
        r"(?:\bSID|__Secure-1PSID|__Secure-1PSIDTS|SAPISID|APISID)\s*=\s*[A-Za-z0-9._/+-]{8,}"
    )
    for path in COMMUNITY + [ROOT / "README.md", ROOT / "CHANGELOG.md"]:
        if not path.exists():
            continue
        text = _read(path)
        assert not bearer.search(text), f"possivel token Bearer real em {path.name}"
        assert not cookie_value.search(text), f"possivel cookie com valor em {path.name}"
