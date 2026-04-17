from __future__ import annotations

import asyncio
import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.core.config import Settings
from app.services.notebook_repository import NotebookRepository
from app.services.notebooklm_service import build_notebook_service
from app.services.storage_state_service import StorageStateService


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "setup":
        return run_setup(project_root=_resolve_project_root(args.project_root))
    if args.command == "start":
        return run_start(project_root=_resolve_project_root(args.project_root), dev_mode=args.dev)
    if args.command == "off":
        return run_off(project_root=_resolve_project_root(args.project_root))
    if args.command == "status":
        return run_status(project_root=_resolve_project_root(args.project_root))
    if args.command == "list":
        return run_list(
            project_root=_resolve_project_root(args.project_root),
            dev_mode=getattr(args, "dev", False),
        )
    if args.command == "delete":
        return run_delete(
            project_root=_resolve_project_root(args.project_root),
            notebook_id=args.notebook_id,
        )

    parser.print_help()
    return 1


def run_setup(project_root: Path) -> int:
    os.chdir(project_root)
    print("[setup] preparando ambiente...")
    venv_dir = project_root / ".venv"
    venv_python = _venv_python(project_root)
    venv_pip = _venv_pip(project_root)

    if not venv_dir.exists():
        print("[setup] criando virtualenv (.venv)")
        _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=project_root)
    else:
        print("[setup] virtualenv ja existe")

    if not venv_pip.exists() or not venv_python.exists():
        print("[setup] erro: virtualenv invalido (python/pip nao encontrados)")
        return 1

    print("[setup] instalando dependencias")
    _run(
        [str(venv_pip), "install", "--disable-pip-version-check", "-q", "-e", ".[dev]"],
        cwd=project_root,
        quiet=True,
    )

    env_example = project_root / ".env.example"
    env_file = project_root / ".env"
    if not env_file.exists():
        if not env_example.exists():
            print("[setup] erro: .env.example nao encontrado")
            return 1
        shutil.copyfile(env_example, env_file)
        print("[setup] .env criado a partir de .env.example")
    else:
        print("[setup] .env ja existe")

    settings = Settings(_env_file=env_file)
    _prepare_directories(settings)
    print("[setup] diretorios preparados")

    print("[setup] validando boot da aplicacao")
    _run(
        [str(venv_python), "-c", "from app.main import app; print(app.title)"],
        cwd=project_root,
        quiet=True,
    )

    print("[setup] concluido")
    return 0


def run_start(project_root: Path, dev_mode: bool = False) -> int:
    os.chdir(project_root)
    settings = Settings(_env_file=project_root / ".env", notebooklm_mode=("mock" if dev_mode else "real"))
    _prepare_directories(settings)

    pid_path = _pid_file(settings)
    log_path = _log_file(settings)

    existing_pid = _read_pid(pid_path)
    if existing_pid is not None:
        if _is_process_running(existing_pid):
            print(f"[start] aplicacao ja em execucao (pid={existing_pid})")
            print(f"[start] log: {log_path}")
            return 0
        pid_path.unlink(missing_ok=True)

    python_bin = _venv_python(project_root)
    if not python_bin.exists():
        python_bin = Path(sys.executable)

    command = [
        str(python_bin),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
    ]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        child_env = os.environ.copy()
        child_env["NOTEBOOKLM_MODE"] = "mock" if dev_mode else "real"
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=project_root,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=child_env,
        )

    if process.poll() is not None:
        print("[start] falha ao iniciar aplicacao; veja o log:")
        print(log_path)
        return 1

    health_ok = _wait_for_http_ready("http://127.0.0.1:8080/health", timeout_seconds=12.0)
    if not health_ok:
        print("[start] aplicacao nao respondeu /health no tempo esperado")
        print(f"[start] log: {log_path}")
        try:
            os.kill(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        return 1

    _write_pid(pid_path, process.pid)
    mode_label = "mock/dev" if dev_mode else "real"
    print(f"[start] aplicacao iniciada em 0.0.0.0:8080 (pid={process.pid}, mode={mode_label})")
    print(f"[start] log: {log_path}")
    return 0


def run_off(project_root: Path) -> int:
    os.chdir(project_root)
    settings = Settings(_env_file=project_root / ".env")
    pid_path = _pid_file(settings)

    pid = _read_pid(pid_path)
    if pid is None:
        print("[off] nenhuma instancia registrada")
        return 0

    if not _is_process_running(pid):
        pid_path.unlink(missing_ok=True)
        print("[off] processo ja estava encerrado; pid limpo")
        return 0

    print(f"[off] encerrando processo pid={pid}")
    os.kill(pid, signal.SIGTERM)

    deadline = time.time() + 8.0
    while time.time() < deadline:
        if not _is_process_running(pid):
            pid_path.unlink(missing_ok=True)
            print("[off] aplicacao encerrada")
            return 0
        time.sleep(0.2)

    print("[off] processo nao encerrou com SIGTERM; enviando SIGKILL")
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    pid_path.unlink(missing_ok=True)
    print("[off] aplicacao encerrada")
    return 0


def run_status(project_root: Path) -> int:
    os.chdir(project_root)
    settings = Settings(_env_file=project_root / ".env")
    pid_path = _pid_file(settings)
    log_path = _log_file(settings)

    pid = _read_pid(pid_path)
    if pid is None or not _is_process_running(pid):
        print("[status] offline")
        print(f"[status] pid_file: {pid_path}")
        print(f"[status] log_file: {log_path}")
        return 0

    print("[status] online")
    print(f"[status] pid: {pid}")
    print("[status] endpoint: http://0.0.0.0:8080")
    print(f"[status] log_file: {log_path}")
    return 0


def run_list(project_root: Path, dev_mode: bool = False) -> int:
    os.chdir(project_root)
    settings, notebook_service, notebook_repository = _build_runtime_for_cli(
        project_root,
        dev_mode=dev_mode,
    )

    local_before = notebook_repository.list_all()

    access = asyncio.run(notebook_service.verify_access())
    if not access.ok:
        print(f"[list] acesso ao NotebookLM indisponivel: {access.detail}")
        print("[list] encontrados no Google: indisponivel")
        print(f"[list] encontrados no banco: {len(local_before)}")
        print("[list] adicionados ao banco: 0")
        print("[list] removidos do banco: 0")
        print("[list] lista final:")
        for item in local_before:
            print(f"  - local_id={item.local_id} notebook_id={item.notebook_id} title={item.title}")
        return 1

    account_notebooks = asyncio.run(notebook_service.list_notebooks())

    print(f"[list] encontrados no Google: {len(account_notebooks)}")
    print(f"[list] encontrados no banco: {len(local_before)}")

    local_map = {item.notebook_id: item for item in local_before}

    imported_count = 0
    for item in account_notebooks:
        notebook_id = str(item.get("id") or item.get("notebook_id") or "").strip()
        if not notebook_id:
            continue
        title = str(item.get("title") or "Notebook")
        source_count = int(item.get("source_count") or 0)
        existing = local_map.get(notebook_id)

        notebook_repository.upsert_notebook(
            notebook_id=notebook_id,
            title=title,
            source_count=source_count,
            artifact_count=(existing.artifact_count if existing else 0),
            origin=(existing.origin if existing else "imported_from_account"),
            metadata=item,
        )
        if existing is None:
            imported_count += 1

    print(f"[list] adicionados ao banco: {imported_count}")

    account_ids = {
        str(item.get("id") or item.get("notebook_id") or "").strip()
        for item in account_notebooks
        if str(item.get("id") or item.get("notebook_id") or "").strip()
    }
    stale_locals = [item for item in local_before if item.notebook_id not in account_ids]
    removed_count = 0
    for item in stale_locals:
        deleted, _ = notebook_repository.delete_by_notebook_id(item.notebook_id)
        if deleted:
            removed_count += 1

    print(f"[list] removidos do banco: {removed_count}")

    final_items = notebook_repository.list_all()
    print("[list] lista final:")
    for item in final_items:
        print(f"  - local_id={item.local_id} notebook_id={item.notebook_id} title={item.title}")

    if stale_locals:
        print("[list] notebooks removidos por nao existirem mais na conta:")
        for item in stale_locals:
            print(f"  - local_id={item.local_id} notebook_id={item.notebook_id} title={item.title}")

    _ = settings
    return 0


def run_delete(project_root: Path, notebook_id: str) -> int:
    os.chdir(project_root)
    _, notebook_service, notebook_repository = _build_runtime_for_cli(project_root)

    local_record = notebook_repository.get_by_notebook_id(notebook_id)
    deleted_remote = False
    deleted_local = False
    details: list[str] = []

    try:
        remote = asyncio.run(notebook_service.get_notebook(notebook_id))
        if remote is None:
            details.append("notebook remoto ja estava ausente")
        else:
            asyncio.run(notebook_service.delete_notebook(notebook_id))
            deleted_remote = True
            details.append("notebook remoto removido")
    except Exception as exc:  # noqa: BLE001
        details.append(f"falha ao remover remoto: {exc.__class__.__name__}")

    if local_record is not None:
        deleted_local, _ = notebook_repository.delete_by_notebook_id(notebook_id)
        if deleted_local:
            details.append("registro local removido")
    else:
        details.append("registro local nao encontrado")

    print(
        "[delete] "
        f"notebook_id={notebook_id} "
        f"deleted_remote={str(deleted_remote).lower()} "
        f"deleted_local={str(deleted_local).lower()}"
    )
    print(f"[delete] detail: {'; '.join(details)}")

    return 0 if deleted_remote or deleted_local else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="notebooklmapi", description="CLI do NotebookLM API")
    subparsers = parser.add_subparsers(dest="command")

    for command in ("setup", "off", "status"):
        sub = subparsers.add_parser(command)
        sub.add_argument(
            "--project-root",
            type=Path,
            default=None,
            help=argparse.SUPPRESS,
        )

    list_sub = subparsers.add_parser("list")
    list_sub.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    list_sub.add_argument(
        "--dev",
        action="store_true",
        help="Executa listagem/sync usando backend mock",
    )

    delete_sub = subparsers.add_parser("delete")
    delete_sub.add_argument("notebook_id", type=str)
    delete_sub.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )

    start_sub = subparsers.add_parser("start")
    start_sub.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    start_sub.add_argument(
        "--dev",
        action="store_true",
        help="Inicia em modo mock/desenvolvimento",
    )

    return parser


def _resolve_project_root(candidate: Path | None) -> Path:
    if candidate is not None:
        root = candidate.resolve()
        if not (root / "pyproject.toml").exists():
            raise SystemExit(f"Projeto invalido: pyproject.toml ausente em {root}")
        return root

    current = Path.cwd().resolve()
    for path in (current, *current.parents):
        if (path / "pyproject.toml").exists():
            return path

    raise SystemExit("Nao foi possivel localizar pyproject.toml no diretorio atual")


def _run(command: list[str], cwd: Path, quiet: bool = False) -> None:
    if quiet:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    else:
        result = subprocess.run(command, cwd=cwd, check=False)  # noqa: S603
    if result.returncode != 0:
        if quiet and result.stdout:
            print(result.stdout)
        joined = " ".join(command)
        raise SystemExit(f"Falha ao executar comando: {joined}")


def _prepare_directories(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    settings.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
    settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    (_pid_file(settings)).parent.mkdir(parents=True, exist_ok=True)


def _build_runtime_for_cli(
    project_root: Path,
    dev_mode: bool = False,
) -> tuple[Settings, object, NotebookRepository]:
    settings = Settings(
        _env_file=project_root / ".env",
        notebooklm_mode=("mock" if dev_mode else "real"),
    )
    _prepare_directories(settings)
    storage_state_service = StorageStateService(settings.storage_state_path)
    notebook_service = build_notebook_service(settings, storage_state_service)
    notebook_repository = NotebookRepository(settings.sqlite_db_path)
    return settings, notebook_service, notebook_repository


def _venv_python(project_root: Path) -> Path:
    if os.name == "nt":
        return project_root / ".venv" / "Scripts" / "python.exe"
    return project_root / ".venv" / "bin" / "python"


def _venv_pip(project_root: Path) -> Path:
    if os.name == "nt":
        return project_root / ".venv" / "Scripts" / "pip.exe"
    return project_root / ".venv" / "bin" / "pip"


def _pid_file(settings: Settings) -> Path:
    return settings.data_dir / "run" / "notebooklmapi.pid"


def _log_file(settings: Settings) -> Path:
    return settings.data_dir / "run" / "notebooklmapi.log"


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _write_pid(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="utf-8")


def _is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_http_ready(url: str, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:  # noqa: S310
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.2)
    return False


if __name__ == "__main__":
    raise SystemExit(main())
    list_sub = subparsers.add_parser("list")
    list_sub.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    list_sub.add_argument(
        "--dev",
        action="store_true",
        help="Executa listagem/sync usando backend mock",
    )
