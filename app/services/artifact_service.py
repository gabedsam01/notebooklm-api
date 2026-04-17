from __future__ import annotations

from pathlib import Path

from app.models.jobs import ArtifactMetadata, JobRecord
from app.utils.file_hash import sha256_file


class ArtifactService:
    def __init__(self, artifacts_dir: Path) -> None:
        self._artifacts_dir = artifacts_dir
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)

    def build_path(self, job_id: str, extension: str) -> Path:
        ext = extension if extension.startswith(".") else f".{extension}"
        return self._artifacts_dir / f"{job_id}{ext}"

    def build_metadata(self, path: Path, content_type: str) -> ArtifactMetadata:
        return ArtifactMetadata(
            file_name=path.name,
            content_type=content_type,
            size_bytes=path.stat().st_size,
            sha256=sha256_file(path),
        )

    def resolve_job_artifact_path(self, job: JobRecord) -> Path | None:
        if not job.artifact_path:
            return None
        path = Path(job.artifact_path)
        if path.is_absolute():
            return path
        return self._artifacts_dir.parent / path
