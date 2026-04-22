
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.models.jobs import (
    AudioSummaryDuration,
    AudioSummaryMode,
    VideoSummaryMode,
    VideoSummaryStyle,
)


class NotebookTargetRequest(BaseModel):
    notebook_id: str | None = Field(default=None, min_length=1)
    local_id: int | None = Field(default=None, ge=1)
    account_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode='after')
    def _validate_target(self) -> 'NotebookTargetRequest':
        if not self.notebook_id and self.local_id is None:
            raise ValueError('Informe notebook_id ou local_id')
        return self


class AudioSummaryOperationRequest(NotebookTargetRequest):
    mode: AudioSummaryMode = AudioSummaryMode.summary
    language: str = Field(default='pt-BR', min_length=2, max_length=20)
    duration: AudioSummaryDuration = AudioSummaryDuration.standard
    focus_prompt: str = Field(default='Em quais aspectos os apresentadores de IA devem se concentrar nesse episodio?', min_length=3, max_length=2_000)
    name: str | None = Field(default=None, max_length=200)


class VideoSummaryOperationRequest(NotebookTargetRequest):
    mode: VideoSummaryMode = VideoSummaryMode.explanatory_video
    style: VideoSummaryStyle = VideoSummaryStyle.summary
    language: str = Field(default='pt-BR', min_length=2, max_length=20)
    visual_style: str | None = Field(default='auto', max_length=100)
    focus_prompt: str = Field(default='Em quais aspectos os apresentadores de IA devem se concentrar?', min_length=3, max_length=2_000)
    name: str | None = Field(default=None, max_length=200)
