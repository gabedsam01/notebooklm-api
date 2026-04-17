from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import get_job_service
from app.models.jobs import JobStatus
from app.services.job_service import JobService

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{job_id}")
async def download_artifact(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> FileResponse:
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job nao encontrado")

    if job.status != JobStatus.completed or not job.artifact_path or job.artifact_metadata is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Artefato ainda nao esta disponivel para este job",
        )

    artifact_path = job_service.resolve_artifact_path(job)
    if artifact_path is None or not artifact_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de artefato nao encontrado")

    return FileResponse(
        path=artifact_path,
        filename=job.artifact_metadata.file_name,
        media_type=job.artifact_metadata.content_type,
    )
