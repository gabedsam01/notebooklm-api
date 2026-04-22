from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from app.api.deps import get_current_account, get_job_service, get_notebook_catalog_service, get_notebook_service
from app.models.account import AccountResponse
from app.models.jobs import GenerateAudioSummaryJobRequest, GenerateVideoSummaryJobRequest
from app.models.operations import AudioSummaryOperationRequest, VideoSummaryOperationRequest
from app.services.job_service import JobService
from app.services.notebook_catalog_service import NotebookCatalogService
from app.services.notebooklm_service import NotebookLMService

router = APIRouter(prefix="/operations", tags=["operations"])


@router.post("/audio-summary", response_model=None)
async def audio_summary_operation(
    payload: AudioSummaryOperationRequest,
    response: Response,
    async_mode: bool = Query(default=True, alias="async"),
    notebook_service: NotebookLMService = Depends(get_notebook_service),
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
    job_service: JobService = Depends(get_job_service),
    account: AccountResponse = Depends(get_current_account),
) -> object:
    await _ensure_access(notebook_service)
    resolved = notebook_catalog.resolve_notebook_id(payload.notebook_id, payload.local_id)

    if async_mode:
        response.status_code = status.HTTP_202_ACCEPTED
        job_payload = GenerateAudioSummaryJobRequest(
            name=payload.name,
            type="generate_audio_summary",
            account_id=account.id,
            notebook_id=resolved.notebook_id,
            local_id=resolved.local_id,
            mode=payload.mode,
            language=payload.language,
            duration=payload.duration,
            focus_prompt=payload.focus_prompt,
        )
        return await job_service.submit_job(job_payload)

    artifact_path, metadata, _ = await job_service.generate_audio_sync(
        account_id=account.id,
        notebook_id=resolved.notebook_id,
        mode=payload.mode.value,
        language=payload.language,
        duration=payload.duration.value,
        focus_prompt=payload.focus_prompt,
    )
    return FileResponse(path=artifact_path, filename=metadata.file_name, media_type=metadata.content_type)


@router.post("/video-summary", response_model=None)
async def video_summary_operation(
    payload: VideoSummaryOperationRequest,
    response: Response,
    async_mode: bool = Query(default=True, alias="async"),
    notebook_service: NotebookLMService = Depends(get_notebook_service),
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
    job_service: JobService = Depends(get_job_service),
    account: AccountResponse = Depends(get_current_account),
) -> object:
    await _ensure_access(notebook_service)
    resolved = notebook_catalog.resolve_notebook_id(payload.notebook_id, payload.local_id)

    if async_mode:
        response.status_code = status.HTTP_202_ACCEPTED
        job_payload = GenerateVideoSummaryJobRequest(
            name=payload.name,
            type="generate_video_summary",
            account_id=account.id,
            notebook_id=resolved.notebook_id,
            local_id=resolved.local_id,
            mode=payload.mode,
            style=payload.style,
            language=payload.language,
            visual_style=payload.visual_style,
            focus_prompt=payload.focus_prompt,
        )
        return await job_service.submit_job(job_payload)

    artifact_path, metadata, _ = await job_service.generate_video_sync(
        account_id=account.id,
        notebook_id=resolved.notebook_id,
        mode=payload.mode.value,
        style=payload.style.value,
        language=payload.language,
        visual_style=payload.visual_style,
        focus_prompt=payload.focus_prompt,
    )
    return FileResponse(path=artifact_path, filename=metadata.file_name, media_type=metadata.content_type)


async def _ensure_access(notebook_service: NotebookLMService) -> None:
    access = await notebook_service.verify_access()
    if not access.ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=access.detail)
