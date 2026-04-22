from __future__ import annotations

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


def test_accounts_create_list_and_default(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)

    initial = client.get("/accounts")
    assert initial.status_code == 200
    data = initial.json()
    assert len(data) == 1
    assert data[0]["id"] == "default"
    assert data[0]["is_default"] is True

    created = client.post("/accounts", json={"alias": "secundaria"})
    assert created.status_code == 201
    created_body = created.json()
    assert created_body["alias"] == "secundaria"
    assert created_body["id"].startswith("acc_")

    listed = client.get("/accounts")
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()]
    assert "default" in ids
    assert created_body["id"] in ids


def test_auth_isolated_by_account_header(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)
    created = client.post("/accounts", json={"alias": "isolation"}).json()
    account_id = created["id"]

    save_resp = client.post(
        "/auth/storage-state",
        headers={"X-NotebookLM-Account-Id": account_id},
        json=_fake_storage_state(),
    )
    assert save_resp.status_code == 200

    default_status = client.get("/auth/status")
    assert default_status.status_code == 200
    assert default_status.json()["storage_state_present"] is False

    account_status = client.get("/auth/status", headers={"X-NotebookLM-Account-Id": account_id})
    assert account_status.status_code == 200
    assert account_status.json()["storage_state_present"] is True
    assert account_status.json()["notebooklm_access_ok"] is True


def test_notebooks_are_scoped_per_account(tmp_path: Path) -> None:
    client, _ = _build_test_client(tmp_path)
    other = client.post("/accounts", json={"alias": "other"}).json()
    other_id = other["id"]

    client.post("/auth/storage-state", json=_fake_storage_state())
    client.post("/auth/storage-state", headers={"X-NotebookLM-Account-Id": other_id}, json=_fake_storage_state())

    default_created = client.post("/notebooks", json={"title": "Default notebook"})
    assert default_created.status_code == 201

    other_created = client.post(
        "/notebooks",
        headers={"X-NotebookLM-Account-Id": other_id},
        json={"title": "Other notebook"},
    )
    assert other_created.status_code == 201

    default_list = client.get("/notebooks")
    assert default_list.status_code == 200
    assert default_list.json()["count"] == 1
    assert default_list.json()["items"][0]["title"] == "Default notebook"
    assert default_list.json()["items"][0]["account_id"] == "default"

    other_list = client.get("/notebooks", headers={"X-NotebookLM-Account-Id": other_id})
    assert other_list.status_code == 200
    assert other_list.json()["count"] == 1
    assert other_list.json()["items"][0]["title"] == "Other notebook"
    assert other_list.json()["items"][0]["account_id"] == other_id
