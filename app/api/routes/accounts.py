from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_account_registry, get_current_account, get_service_factory
from app.models.account import AccountCreateRequest, AccountResponse, AccountUpdateStatusRequest
from app.services.account_keepalive_service import AccountKeepaliveService
from app.services.account_registry_service import AccountRegistryService
from app.services.notebooklm_factory import NotebookLMServiceFactory

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreateRequest,
    registry: AccountRegistryService = Depends(get_account_registry),
) -> AccountResponse:
    return registry.create_account(alias=payload.alias, make_default=payload.make_default)


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    registry: AccountRegistryService = Depends(get_account_registry),
) -> list[AccountResponse]:
    return registry.list_accounts()


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    registry: AccountRegistryService = Depends(get_account_registry),
) -> AccountResponse:
    account = registry.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("/{account_id}/status", response_model=AccountResponse)
async def get_account_status(
    account_id: str,
    registry: AccountRegistryService = Depends(get_account_registry),
) -> AccountResponse:
    account = registry.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("/{account_id}/verify", response_model=AccountResponse)
async def verify_account(
    account_id: str,
    registry: AccountRegistryService = Depends(get_account_registry),
    factory: NotebookLMServiceFactory = Depends(get_service_factory),
) -> AccountResponse:
    account = registry.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    access = await factory.get_service(account_id).verify_access()
    if access.ok:
        return registry.touch_verified(account_id, None, healthy=True)
    lowered = access.detail.lower()
    status_label = "challenge_required" if any(token in lowered for token in ("challenge", "2fa", "captcha")) else "expired"
    return registry.update_status(account_id, status_label, access.detail)


@router.post("/{account_id}/refresh", response_model=AccountResponse)
async def refresh_account(
    account_id: str,
    registry: AccountRegistryService = Depends(get_account_registry),
    factory: NotebookLMServiceFactory = Depends(get_service_factory),
) -> AccountResponse:
    account = registry.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    access = await factory.get_service(account_id).verify_access()
    if access.ok:
        return registry.touch_verified(account_id, "Sessao reutilizada com sucesso.", healthy=True)
    lowered = access.detail.lower()
    status_label = "challenge_required" if any(token in lowered for token in ("challenge", "2fa", "captcha")) else "expired"
    return registry.update_status(account_id, status_label, access.detail)


@router.post("/{account_id}/disable", response_model=AccountResponse)
async def disable_account(
    account_id: str,
    payload: AccountUpdateStatusRequest,
    registry: AccountRegistryService = Depends(get_account_registry),
) -> AccountResponse:
    return registry.update_status(account_id, "disabled", payload.detail)


@router.post("/{account_id}/enable", response_model=AccountResponse)
async def enable_account(
    account_id: str,
    payload: AccountUpdateStatusRequest,
    registry: AccountRegistryService = Depends(get_account_registry),
) -> AccountResponse:
    return registry.update_status(account_id, "warming", payload.detail)


@router.post("/{account_id}/bootstrap", response_model=AccountResponse)
async def bootstrap_account(
    account_id: str,
    registry: AccountRegistryService = Depends(get_account_registry),
) -> AccountResponse:
    account = registry.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return registry.update_status(account_id, "warming", "Bootstrap iniciado. Faça o upload do storage_state para concluir.")
