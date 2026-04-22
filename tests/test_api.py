from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _build_test_client(tmp_path: Path) -> tuple[TestClient, Settings]:
    data_dir = tmp_path / "data"
    settings = Settings(
        app_host="0.0.0.0",
        app_port=8080,
        data_dir=data_dir,
        jobs_dir=data_dir / "jobs",
        artifacts_dir=data_dir / "artifacts",
        temp_dir=data_dir / "tmp",
        storage_state_path=data_dir / "auth" / "storage_state.json",
        accounts_dir=data_dir / "accounts",
        sqlite_db_path=data_dir / "notebooks.db",
        notebooklm_mode="mock",
        worker_poll_interval_seconds=0.01,
    )
    app = create_app(settings)
    return TestClient(app), settings


def _fake_storage_state() -> dict[str, object]:
    return {
        "cookies": [
            {
                "name": "SID",
                "value": "fake-session",
                "domain": ".google.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }
        ],
        "origins": [],
    }


def _seed_auth(client: TestClient, account_id: str | None = None) -> None:
    headers = {"X-NotebookLM-Account-Id": account_id} if account_id else None
    response = client.post("/auth/storage-state", headers=headers, json=_fake_storage_state())
    assert response.status_code == 200


def _create_notebook(client: TestClient, title: str = "Notebook Teste", account_id: str | None = None) -> tuple[str, int]:
    headers = {"X-NotebookLM-Account-Id": account_id} if account_id else None
    response = client.post("/notebooks", headers=headers, json={"title": title})
    assert response.status_code == 201
    return response.json()["notebook_id"], response.json()["local_id"]


def _wait_job_done(client: TestClient, job_id: str, account_id: str | None = None, timeout_seconds: float = 6.0) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    latest: dict[str, object] | None = None
    headers = {"X-NotebookLM-Account-Id": account_id} if account_id else None

    while time.time() < deadline:
        response = client.get(f"/jobs/{job_id}", headers=headers)
        assert response.status_code == 200
        latest = response.json()
        if latest["status"] in {"completed", "failed"}:
            return latest
        time.sleep(0.05)

    raise AssertionError(f"Job {job_id} nao finalizou. Ultimo estado: {latest}")


def test_health_endpoint_and_web_home(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    home_response = client.get("/")
    assert home_response.status_code == 200
    assert "NotebookLM API" in home_response.text


def test_auth_storage_state_status_and_assisted_login_flow(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)

    status_before = client.get("/auth/status")
    assert status_before.status_code == 200
    assert status_before.json()["storage_state_present"] is False

    start_response = client.post("/auth/login/start")
    assert start_response.status_code == 200
    session_id = start_response.json()["session_id"]

    complete_response = client.post(
        "/auth/login/complete",
        json={
            "session_id": session_id,
            "storage_state": _fake_storage_state(),
        },
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["completed"] is True

    status_after = client.get("/auth/status")
    assert status_after.status_code == 200
    data = status_after.json()
    assert data["storage_state_present"] is True
    assert data["storage_state_valid"] is True
    assert data["cookie_count"] == 1
    assert data["notebooklm_access_ok"] is True


def test_notebooks_are_persisted_in_sqlite_and_listed_by_api(tmp_path: Path) -> None:
    client, settings = _build_test_client(tmp_path)
    _seed_auth(client)

    notebook_id, local_id = _create_notebook(client, title="Notebook Persistido")
    assert notebook_id
    assert local_id > 0
    assert settings.sqlite_db_path.exists()

    list_response = client.get("/notebooks")
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["count"] >= 1
    assert any(item["notebook_id"] == notebook_id for item in body["items"])
    assert all(item["account_id"] == "default" for item in body["items"])


def test_sources_single_and_batch_accept_notebook_id_or_local_id(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)
    _seed_auth(client)
    notebook_id, local_id = _create_notebook(client, title="Notebook Fontes")

    single_response = client.post(
        "/sources/text",
        json={
            "local_id": local_id,
            "title": "Fonte 1",
            "content": "Conteudo de exemplo",
        },
    )
    assert single_response.status_code == 200
    assert single_response.json()["added_count"] == 1
    assert len(single_response.json()["source_ids"]) == 1

    batch_response = client.post(
        "/sources/batch",
        json={
            "notebook_id": notebook_id,
            "sources": [
                {"title": "Fonte 2", "content": "Conteudo 2"},
                {"title": "Fonte 3", "content": "Conteudo 3"},
            ],
        },
    )
    assert batch_response.status_code == 200
    assert batch_response.json()["added_count"] == 2
    assert len(batch_response.json()["source_ids"]) == 2


def test_sync_imports_missing_account_notebooks(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)
    _seed_auth(client)

    created = client.post("/notebooks", json={"title": "Notebook Apenas Conta"})
    assert created.status_code == 201
    sync_response = client.post("/notebooks/sync")
    assert sync_response.status_code == 200
    assert sync_response.json()["account_id"] == "default"
    assert sync_response.json()["found_in_account"] >= 1


def test_audio_job_async_with_debug_logs_and_artifact(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)
    _seed_auth(client)

    notebook_id, _ = _create_notebook(client, title="Notebook Audio")
    client.post(
        "/sources/text",
        json={
            "notebook_id": notebook_id,
            "title": "Base",
            "content": "Texto base para gerar resumo em audio.",
        },
    )

    create_job_response = client.post(
        "/operations/audio-summary?async=true",
        json={
            "notebook_id": notebook_id,
            "mode": "debate",
            "language": "pt-BR",
            "duration": "standard",
            "focus_prompt": "Em quais aspectos os apresentadores de IA devem se concentrar nesse episodio?",
        },
    )
    assert create_job_response.status_code == 202
    job_id = create_job_response.json()["id"]

    final_job = _wait_job_done(client, job_id)
    assert final_job["status"] == "completed"
    assert final_job["artifact_path"]
    assert final_job["duration_ms"] is not None
    assert len(final_job["logs"]) > 0
    assert final_job["account_id"] == "default"

    artifact_response = client.get(f"/artifacts/{job_id}")
    assert artifact_response.status_code == 200
    assert artifact_response.headers["content-type"].startswith("audio/")


def test_sync_audio_and_video_endpoints_return_binary(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)
    _seed_auth(client)
    notebook_id, local_id = _create_notebook(client, title="Notebook Sync")
    client.post(
        "/sources/text",
        json={
            "local_id": local_id,
            "title": "Base",
            "content": "Texto para geração síncrona.",
        },
    )

    audio_response = client.post(
        "/operations/audio-summary?async=false",
        json={
            "notebook_id": notebook_id,
            "mode": "summary",
            "language": "pt-BR",
            "duration": "standard",
            "focus_prompt": "Resuma o conteúdo.",
        },
    )
    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"].startswith("audio/")

    video_response = client.post(
        "/operations/video-summary?async=false",
        json={
            "local_id": local_id,
            "mode": "explanatory_video",
            "style": "summary",
            "language": "pt-BR",
            "visual_style": "auto",
            "focus_prompt": "Explique o conteúdo.",
        },
    )
    assert video_response.status_code == 200
    assert video_response.headers["content-type"].startswith("video/")
