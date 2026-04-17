from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class NotebookTargetFields(BaseModel):
    notebook_id: str | None = Field(default=None, min_length=1)
    local_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_target(self) -> "NotebookTargetFields":
        if not self.notebook_id and self.local_id is None:
            raise ValueError("Informe notebook_id ou local_id")
        return self


class TextSourceInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=120_000)


class AddSingleTextSourceRequest(NotebookTargetFields, TextSourceInput):
    pass


class AddBatchTextSourcesRequest(NotebookTargetFields):
    sources: list[TextSourceInput] = Field(min_length=1, max_length=100)


class SourceMutationResponse(BaseModel):
    notebook_id: str
    added_count: int
    source_ids: list[str] = Field(default_factory=list)
