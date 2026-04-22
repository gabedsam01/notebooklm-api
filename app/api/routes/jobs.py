from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_account, get_job_service
from app.models.account import AccountResponse
from app.models.jobs import JobListResponse, JobRecord, JobRequest
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRecord, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    payload: JobRequest,
    account: AccountResponse = Depends(get_current_account),
    job_service: JobService = Depends(get_job_service),
) -> JobRecord:
    if getattr(payload, "account_id", None) is None:
        payload = payload.model_copy(update={"account_id": account.id})
    return await job_service.submit_job(payload)


@router.get("/{job_id}", response_model=JobRecord)
async def get_job(job_id: str, job_service: JobService = Depends(get_job_service)) -> JobRecord:
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job nao encontrado")
    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    job_id: str | None = Query(default=None),
    name: str | None = Query(default=None),
    account: AccountResponse = Depends(get_current_account),
    job_service: JobService = Depends(get_job_service),
) -> JobListResponse:
    items = job_service.list_jobs(job_id=job_id, name=name, account_id=account.id)
    return JobListResponse(count=len(items), items=items)
