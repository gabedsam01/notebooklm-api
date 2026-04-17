from __future__ import annotations

import os
from pathlib import Path

from app.cli import (
    _build_parser,
    _is_process_running,
    _read_pid,
    _resolve_project_root,
    _write_pid,
    run_list,
    run_off,
    run_status,
)
from app.core.config import Settings
from app.services.notebook_repository import NotebookRepository
from app.services.notebooklm_service import NotebookAccessCheck


def _make_project_root(tmp_path: Path) -> Path:
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='0.0.1'\n",
        encoding="utf-8",
    )
    (project_root / ".env").write_text(
        "DATA_DIR='data'\nNOTEBOOKLM_MODE='real'\n",
        encoding="utf-8",
    )
    return project_root


def test_settings_default_mode_is_real() -> None:
    settings = Settings(_env_file=None)
    assert settings.notebooklm_mode == "real"


def test_cli_parser_accepts_start_dev_and_list() -> None:
    parser = _build_parser()
    parsed = parser.parse_args(["start", "--dev"])
    assert parsed.command == "start"
    assert parsed.dev is True

    parsed_list = parser.parse_args(["list"])
    assert parsed_list.command == "list"

    parsed_list_dev = parser.parse_args(["list", "--dev"])
    assert parsed_list_dev.command == "list"
    assert parsed_list_dev.dev is True

    parsed_delete = parser.parse_args(["delete", "nb-123"])
    assert parsed_delete.command == "delete"
    assert parsed_delete.notebook_id == "nb-123"


def test_pid_helpers_roundtrip() -> None:
    assert _is_process_running(os.getpid()) is True


def test_read_write_pid_file(tmp_path: Path) -> None:
    pid_file = tmp_path / "run" / "app.pid"
    _write_pid(pid_file, 12345)
    assert _read_pid(pid_file) == 12345

    pid_file.write_text("invalid", encoding="utf-8")
    assert _read_pid(pid_file) is None


def test_resolve_project_root_from_explicit_path(tmp_path: Path) -> None:
    project_root = _make_project_root(tmp_path)
    resolved = _resolve_project_root(project_root)
    assert resolved == project_root.resolve()


def test_status_offline_and_off_handles_stale_pid(tmp_path: Path, capsys: object) -> None:
    project_root = _make_project_root(tmp_path)

    status_code = run_status(project_root)
    captured = capsys.readouterr()
    assert status_code == 0
    assert "[status] offline" in captured.out

    pid_file = project_root / "data" / "run" / "notebooklmapi.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text("999999", encoding="utf-8")

    off_code = run_off(project_root)
    captured_off = capsys.readouterr()
    assert off_code == 0
    assert "ja estava encerrado" in captured_off.out
    assert not pid_file.exists()


def test_cli_list_syncs_imports_and_removes_orphans(
    tmp_path: Path,
    monkeypatch: object,
    capsys: object,
) -> None:
    project_root = _make_project_root(tmp_path)
    settings = Settings(
        _env_file=project_root / ".env",
        data_dir=project_root / "data",
        sqlite_db_path=project_root / "data" / "notebooks.db",
    )
    repo = NotebookRepository(settings.sqlite_db_path)
    repo.upsert_notebook(
        notebook_id="nb-old",
        title="Notebook local antigo",
        source_count=1,
        artifact_count=0,
        origin="local_created",
    )

    class _FakeNotebookService:
        async def verify_access(self) -> NotebookAccessCheck:
            return NotebookAccessCheck(ok=True, detail="ok")

        async def list_notebooks(self) -> list[dict[str, object]]:
            return [
                {"id": "nb-1", "title": "Notebook 1", "source_count": 2},
                {"id": "nb-2", "title": "Notebook 2", "source_count": 1},
            ]

    def _fake_runtime(_: Path, dev_mode: bool = False) -> tuple[Settings, _FakeNotebookService, NotebookRepository]:
        _ = dev_mode
        return settings, _FakeNotebookService(), repo

    monkeypatch.setattr("app.cli._build_runtime_for_cli", _fake_runtime)

    code = run_list(project_root)
    output = capsys.readouterr().out

    assert code == 0
    assert "encontrados no Google: 2" in output
    assert "encontrados no banco: 1" in output
    assert "adicionados ao banco: 2" in output
    assert "removidos do banco: 1" in output
    assert len(repo.list_all()) == 2


def test_cli_list_when_remote_unavailable_still_reports_local_state(
    tmp_path: Path,
    monkeypatch: object,
    capsys: object,
) -> None:
    project_root = _make_project_root(tmp_path)
    settings = Settings(
        _env_file=project_root / ".env",
        data_dir=project_root / "data",
        sqlite_db_path=project_root / "data" / "notebooks.db",
    )
    repo = NotebookRepository(settings.sqlite_db_path)
    repo.upsert_notebook(
        notebook_id="nb-local",
        title="Notebook local",
        source_count=0,
        artifact_count=0,
        origin="local_created",
    )

    class _UnavailableNotebookService:
        async def verify_access(self) -> NotebookAccessCheck:
            return NotebookAccessCheck(ok=False, detail="sem sessao")

        async def list_notebooks(self) -> list[dict[str, object]]:
            return []

    def _fake_runtime(_: Path, dev_mode: bool = False) -> tuple[Settings, _UnavailableNotebookService, NotebookRepository]:
        _ = dev_mode
        return settings, _UnavailableNotebookService(), repo

    monkeypatch.setattr("app.cli._build_runtime_for_cli", _fake_runtime)

    code = run_list(project_root)
    output = capsys.readouterr().out

    assert code == 1
    assert "acesso ao NotebookLM indisponivel" in output
    assert "encontrados no banco: 1" in output
    assert "adicionados ao banco: 0" in output
    assert "removidos do banco: 0" in output
    assert "nb-local" in output
