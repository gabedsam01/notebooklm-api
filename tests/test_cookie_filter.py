import pytest
from pathlib import Path
from app.models.auth import StorageCookie, StorageStatePayload
from app.services.notebooklm_auth_service import NotebookLMAuthService
from app.services.storage_state_service import StorageStateService


@pytest.fixture
def auth_service(tmp_path):
    storage_path = tmp_path / "storage_state.json"
    storage_service = StorageStateService(storage_path)
    return NotebookLMAuthService(storage_service)


def test_cookie_normalization():
    # Test expirationDate -> expires and sameSite mapping
    raw_data = {
        "name": "SID",
        "value": "test_value",
        "domain": ".google.com",
        "expirationDate": 1234567890.123,
        "sameSite": "no_restriction",
        "hostOnly": True,  # Irrelevant field, should be ignored
        "session": False
    }
    
    cookie = StorageCookie.model_validate(raw_data)
    
    assert cookie.name == "SID"
    assert cookie.expires == 1234567890.123
    assert cookie.sameSite == "None"
    
    # Extra fields should be ignored (extra="ignore")
    dumped = cookie.model_dump(exclude_unset=True)
    assert "hostOnly" not in dumped
    assert "session" not in dumped


def test_cookie_filter_logic(auth_service):
    payload_data = [
        {"name": "SID", "value": "1", "domain": ".google.com"},
        {"name": "HSID", "value": "2", "domain": ".google.com"},
        {"name": "__Secure-1PSID", "value": "3", "domain": "google.com"},
        {"name": "__Secure-3PSIDCC", "value": "4", "domain": "notebooklm.google.com"},
        {"name": "_ga", "value": "5", "domain": ".google.com"},  # Irrelevant name
        {"name": "NID", "value": "6", "domain": ".google.com"},  # Irrelevant name
        {"name": "SID", "value": "7", "domain": "example.com"},  # Irrelevant domain
    ]
    
    payload = StorageStatePayload.model_validate(payload_data)
    filtered_payload, received, kept, names, has_min = auth_service.filter_payload(payload)
    
    assert received == 7
    assert kept == 4
    assert set(names) == {"SID", "HSID", "__Secure-1PSID", "__Secure-3PSIDCC"}
    assert has_min is True
    
    # Verify the remaining cookies
    for c in filtered_payload.cookies:
        assert c.domain in {".google.com", "google.com", "notebooklm.google.com"}
        assert c.name in {"SID", "HSID", "__Secure-1PSID", "__Secure-3PSIDCC"}


def test_insufficient_payload(auth_service):
    # Only irrelevant cookies
    payload_data = [
        {"name": "_ga", "value": "1", "domain": ".google.com"},
        {"name": "NID", "value": "2", "domain": ".google.com"},
    ]
    
    payload = StorageStatePayload.model_validate(payload_data)
    _, received, kept, names, has_min = auth_service.filter_payload(payload)
    
    assert received == 2
    assert kept == 0
    assert has_min is False


def test_save_storage_state_with_filtering(auth_service):
    payload_data = [
        {"name": "SID", "value": "1", "domain": ".google.com"},
        {"name": "AEC", "value": "2", "domain": ".google.com"},
    ]
    payload = StorageStatePayload.model_validate(payload_data)
    
    response = auth_service.save_storage_state(payload)
    
    assert response.storage_state_present is True
    assert response.cookie_count_received == 2
    assert response.cookie_count_kept == 1
    assert response.kept_cookie_names == ["SID"]
    assert response.has_minimum_auth_cookies is True
    assert "filtrado e salvo com 1 cookies relevantes" in response.detail
    
    # Verify the saved file
    saved_data = auth_service._storage_state_service.load()
    assert saved_data is not None
    assert len(saved_data["cookies"]) == 1
    assert saved_data["cookies"][0]["name"] == "SID"


def test_save_storage_state_incomplete(auth_service):
    payload_data = [
        {"name": "NID", "value": "1", "domain": ".google.com"}
    ]
    payload = StorageStatePayload.model_validate(payload_data)
    
    response = auth_service.save_storage_state(payload)
    
    assert response.cookie_count_received == 1
    assert response.cookie_count_kept == 0
    assert response.has_minimum_auth_cookies is False
    assert "fraco/incompleto para autenticação" in response.detail
