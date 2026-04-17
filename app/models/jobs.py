from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.sources import TextSourceInput


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class JobType(str, Enum):
    create_notebook = "create_notebook"
    add_source = "add_source"
    add_sources_batch = "add_sources_batch"
    generate_audio_summary = "generate_audio_summary"
    generate_video_summary = "generate_video_summary"
    delete_notebook = "delete_notebook"


class AudioSummaryMode(str, Enum):
    detailed_analysis = "detailed_analysis"
    summary = "summary"
    critical_review = "critical_review"
    debate = "debate"


class AudioSummaryDuration(str, Enum):
    short = "short"
    standard = "standard"
    long = "long"


class VideoSummaryMode(str, Enum):
    explanatory_video = "explanatory_video"


class VideoSummaryStyle(str, Enum):
    summary = "summary"


class NotebookTargetMixin(BaseModel):
    notebook_id: str | None = Field(default=None, min_length=1)
    local_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_target(self) -> "NotebookTargetMixin":
        if not self.notebook_id and self.local_id is None:
            raise ValueError("Informe notebook_id ou local_id")
        return self


class BaseJobRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)


class CreateNotebookJobRequest(BaseJobRequest):
    type: Literal[JobType.create_notebook.value]
    title: str = Field(min_length=1, max_length=200)


class AddSourceJobRequest(BaseJobRequest, NotebookTargetMixin):
    type: Literal[JobType.add_source.value]
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=120_000)


class AddSourcesBatchJobRequest(BaseJobRequest, NotebookTargetMixin):
    type: Literal[JobType.add_sources_batch.value]
    sources: list[TextSourceInput] = Field(min_length=1, max_length=100)


class GenerateAudioSummaryJobRequest(BaseJobRequest, NotebookTargetMixin):
    type: Literal[JobType.generate_audio_summary.value]
    mode: AudioSummaryMode = AudioSummaryMode.summary
    language: str = Field(default="pt-BR", min_length=2, max_length=20)
    duration: AudioSummaryDuration = AudioSummaryDuration.standard
    focus_prompt: str = Field(
        default=(
            "Em quais aspectos os apresentadores de IA devem se concentrar nesse episodio?"
        ),
        min_length=3,
        max_length=2_000,
    )


class GenerateVideoSummaryJobRequest(BaseJobRequest, NotebookTargetMixin):
    type: Literal[JobType.generate_video_summary.value]
    mode: VideoSummaryMode = VideoSummaryMode.explanatory_video
    style: VideoSummaryStyle = VideoSummaryStyle.summary
    language: str = Field(default="pt-BR", min_length=2, max_length=20)
    visual_style: str | None = Field(default="auto", max_length=100)
    focus_prompt: str = Field(
        default="Em quais aspectos os apresentadores de IA devem se concentrar?",
        min_length=3,
        max_length=2_000,
    )


class DeleteNotebookJobRequest(BaseJobRequest, NotebookTargetMixin):
    type: Literal[JobType.delete_notebook.value]


JobRequest = Annotated[
    (
        CreateNotebookJobRequest
        | AddSourceJobRequest
        | AddSourcesBatchJobRequest
        | GenerateAudioSummaryJobRequest
        | GenerateVideoSummaryJobRequest
        | DeleteNotebookJobRequest
    ),
    Field(discriminator="type"),
]


class ArtifactMetadata(BaseModel):
    file_name: str
    content_type: str
    size_bytes: int
    sha256: str


class JobLogEntry(BaseModel):
    at: datetime
    stage: str
    message: str


class JobRecord(BaseModel):
    id: str
    name: str
    type: JobType
    status: JobStatus
    input: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    duration_ms: int | None = None
    notebook_id: str | None = None
    artifact_path: str | None = None
    artifact_metadata: ArtifactMetadata | None = None
    logs: list[JobLogEntry] = Field(default_factory=list)


class JobListResponse(BaseModel):
    count: int
    items: list[JobRecord]
