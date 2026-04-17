from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.models.jobs import JobRecord


class JobRepository(Protocol):
    def save(self, job: JobRecord) -> None:
        ...

    def get(self, job_id: str) -> JobRecord | None:
        ...

    def list(self, job_id: str | None = None, name: str | None = None) -> list[JobRecord]:
        ...


class LocalJsonJobRepository:
    def __init__(self, jobs_dir: Path) -> None:
        self._jobs_dir = jobs_dir
        self._jobs_dir.mkdir(parents=True, exist_ok=True)

    def save(self, job: JobRecord) -> None:
        destination = self._job_file(job.id)
        destination.parent.mkdir(parents=True, exist_ok=True)

        temp_path = destination.with_suffix(".tmp")
        temp_path.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        temp_path.replace(destination)

    def get(self, job_id: str) -> JobRecord | None:
        file_path = self._job_file(job_id)
        if not file_path.exists():
            return None
        return JobRecord.model_validate_json(file_path.read_text(encoding="utf-8"))

    def list(self, job_id: str | None = None, name: str | None = None) -> list[JobRecord]:
        if job_id:
            job = self.get(job_id)
            return [job] if job is not None else []

        jobs: list[JobRecord] = []
        for item in sorted(self._jobs_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True):
            try:
                job = JobRecord.model_validate_json(item.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if name and job.name != name:
                continue
            jobs.append(job)
        return jobs

    def _job_file(self, job_id: str) -> Path:
        return self._jobs_dir / f"{job_id}.json"
