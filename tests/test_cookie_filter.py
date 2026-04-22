from pathlib import Path

import pytest

from app.models.auth import StorageCookie, StorageStatePayload
from app.services.account_auth_service import AccountAuthService
from app.services.account_registry_service import AccountRegistryService
from app.core.config import Settings


@pytest.fixture
def auth_service(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", notebooklm_mode="mock")
    registry = AccountRegistryService(settings)
    registry.ensure_default_account()
    return AccountAuthService(registry)


def test_cookie_normalization():
    raw_data = {
        "name": "SID",
        "value": "test_value",
        "domain": ".google.com",
        "expirationDate": 1234567890.123,
        "sameSite": "no_restriction",
        "hostOnly": True,
        "session": False,
    }

    cookie = StorageCookie.model_validate(raw_data)

    assert cookie.name == "SID"
    assert cookie.expires == 1234567890.123
    assert cookie.sameSite == "None"

    dumped = cookie.model_dump(exclude_unset=True)
    assert "hostOnly" not in dumped
    assert "session" not in dumped


def test_cookie_filter_logic(auth_service):
    payload_data = [
        {"name": "SID", "value": "1", "domain": ".google.com"},
        {"name": "HSID", "value": "2", "domain": ".google.com"},
        {"name": "__Secure-1PSID", "value": "3", "domain": "google.com"},
        {"name": "__Secure-3PSIDCC", "value": "4", "domain": "notebooklm.google.com"},
        {"name": "_ga", "value": "5", "domain": ".google.com"},
        {"name": "NID", "value": "6", "domain": ".google.com"},
        {"name": "SID", "value": "7", "domain": "example.com"},
    ]

    payload = StorageStatePayload.model_validate(payload_data)
    filtered_payload, received, kept, names, has_min = auth_service.filter_payload(payload)

    assert received == 7
    assert kept == 4
    assert set(names) == {"SID", "HSID", "__Secure-1PSID", "__Secure-3PSIDCC"}
    assert has_min is True

    for c in filtered_payload.cookies:
        assert c.domain in {".google.com", "google.com", "notebooklm.google.com"}
        assert c.name in {"SID", "HSID", "__Secure-1PSID", "__Secure-3PSIDCC"}


def test_insufficient_payload(auth_service):
    payload_data = [
        {"name": "_ga", "value": "1", "domain": ".google.com"},
        {"name": "NID", "value": "2", "domain": ".google.com"},
    ]

    payload = StorageStatePayload.model_validate(payload_data)
    _, received, kept, names, has_min = auth_service.filter_payload(payload)

    assert received == 2
    assert kept == 0
    assert names == []
    assert has_min is False


def test_save_storage_state_with_filtering(auth_service):
    payload_data = [
        {"name": "SID", "value": "1", "domain": ".google.com"},
        {"name": "AEC", "value": "2", "domain": ".google.com"},
    ]
    payload = StorageStatePayload.model_validate(payload_data)

    response = auth_service.save_storage_state("default", payload)

    assert response.storage_state_present is True
    assert response.cookie_count_received == 2
    assert response.cookie_count_kept == 1
    assert response.kept_cookie_names == ["SID"]
    assert response.has_minimum_auth_cookies is True
    assert "conta default" in response.detail
