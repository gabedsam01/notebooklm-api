from __future__ import annotations

import json
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.models.auth import StorageStatePayload
from app.models.jobs import (
    AudioSummaryDuration,
    AudioSummaryMode,
    GenerateAudioSummaryJobRequest,
    GenerateVideoSummaryJobRequest,
    VideoSummaryMode,
    VideoSummaryStyle,
)
from app.models.sources import TextSourceInput

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    auth_status = await request.app.state.auth_service.get_status(request.app.state.notebook_service)
    jobs = request.app.state.job_service.list_jobs()[:20]
    notebooks = request.app.state.notebook_catalog_service.list_persisted()[:50]
    context = {
        "request": request,
        "auth_status": auth_status,
        "jobs": jobs,
        "notebooks": notebooks,
    }
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="index.html",
        context=context,
    )


@router.post("/web/auth/storage-state", response_class=HTMLResponse)
async def web_save_storage_state(
    request: Request,
    storage_state_json: str = Form(...),
) -> HTMLResponse:
    started = time.perf_counter()
    try:
        parsed = json.loads(storage_state_json)
        payload = StorageStatePayload.model_validate(parsed)
        result = request.app.state.auth_service.save_storage_state(payload)
        response = _render_result(
            request,
            variant="success",
            title="Storage state salvo",
            message=result.detail,
            elapsed_ms=_elapsed_ms(started),
        )
        response.headers["HX-Refresh"] = "true"
        return response
    except Exception as exc:  # noqa: BLE001
        return _render_result(
            request,
            variant="error",
            title="Falha ao salvar storage state",
            message=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=_elapsed_ms(started),
        )


@router.post("/web/notebooks/create", response_class=HTMLResponse)
async def web_create_notebook(
    request: Request,
    title: str = Form(...),
) -> HTMLResponse:
    started = time.perf_counter()
    try:
        notebook = await request.app.state.notebook_catalog_service.create_and_persist(title.strip())
        return _render_result(
            request,
            variant="success",
            title="Notebook criado",
            message="Notebook criado e persistido com sucesso.",
            details={
                "notebook_id": notebook.notebook_id,
                "local_id": notebook.local_id,
                "source_count": notebook.source_count,
            },
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as exc:  # noqa: BLE001
        return _render_result(
            request,
            variant="error",
            title="Falha ao criar notebook",
            message=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=_elapsed_ms(started),
        )


@router.post("/web/notebooks/sync", response_class=HTMLResponse)
async def web_sync_notebooks(request: Request) -> HTMLResponse:
    started = time.perf_counter()
    try:
        result = await request.app.state.notebook_catalog_service.sync_from_account()
        return _render_result(
            request,
            variant="success",
            title="Sincronizacao concluida",
            message=result.detail,
            details=result.model_dump(mode="json"),
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as exc:  # noqa: BLE001
        return _render_result(
            request,
            variant="error",
            title="Falha na sincronizacao",
            message=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=_elapsed_ms(started),
        )


@router.delete("/web/notebooks/{notebook_id}", response_class=HTMLResponse)
async def web_delete_notebook(request: Request, notebook_id: str) -> HTMLResponse:
    started = time.perf_counter()
    try:
        result = await request.app.state.notebook_catalog_service.delete_notebook(notebook_id=notebook_id)
        variant = "success" if result.status != "failed" else "error"
        title = "Notebook removido" if result.status != "failed" else "Falha ao remover notebook"
        return _render_result(
            request,
            variant=variant,
            title=title,
            message=result.detail,
            details=result.model_dump(mode="json"),
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as exc:  # noqa: BLE001
        return _render_result(
            request,
            variant="error",
            title="Falha ao remover notebook",
            message=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=_elapsed_ms(started),
        )


@router.get("/web/notebooks/list", response_class=HTMLResponse)
async def web_list_notebooks(request: Request) -> HTMLResponse:
    notebooks = request.app.state.notebook_catalog_service.list_persisted()[:100]
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="partials/notebooks_table.html",
        context={
            "request": request,
            "notebooks": notebooks,
        },
    )


@router.post("/web/sources/text", response_class=HTMLResponse)
async def web_add_source_text(
    request: Request,
    notebook_id: str = Form(default=""),
    local_id: str = Form(default=""),
    title: str = Form(...),
    content: str = Form(...),
) -> HTMLResponse:
    started = time.perf_counter()
    try:
        source = request.app.state.source_builder_service.normalize_single(title, content)
        resolved = request.app.state.notebook_catalog_service.resolve_notebook_id(
            notebook_id=notebook_id.strip() or None,
            local_id=int(local_id) if local_id.strip() else None,
        )
        source_id = await request.app.state.notebook_service.add_text_source(
            notebook_id=resolved.notebook_id,
            title=source.title,
            content=source.content,
        )
        await request.app.state.notebook_catalog_service.refresh_and_get(resolved.notebook_id)

        return _render_result(
            request,
            variant="success",
            title="Fonte adicionada",
            message="Fonte textual adicionada com sucesso.",
            details={
                "notebook_id": resolved.notebook_id,
                "local_id": resolved.local_id,
                "source_ids": [source_id] if source_id else [],
            },
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as exc:  # noqa: BLE001
        return _render_result(
            request,
            variant="error",
            title="Falha ao adicionar fonte",
            message=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=_elapsed_ms(started),
        )


@router.post("/web/sources/batch", response_class=HTMLResponse)
async def web_add_source_batch(
    request: Request,
    notebook_id: str = Form(default=""),
    local_id: str = Form(default=""),
    sources_json: str = Form(...),
) -> HTMLResponse:
    started = time.perf_counter()
    try:
        parsed = json.loads(sources_json)
        sources = [TextSourceInput.model_validate(item) for item in parsed]
        normalized = request.app.state.source_builder_service.normalize_batch(sources)
        resolved = request.app.state.notebook_catalog_service.resolve_notebook_id(
            notebook_id=notebook_id.strip() or None,
            local_id=int(local_id) if local_id.strip() else None,
        )
        source_ids = await request.app.state.notebook_service.add_text_sources_batch(
            notebook_id=resolved.notebook_id,
            sources=[item.model_dump() for item in normalized],
        )
        await request.app.state.notebook_catalog_service.refresh_and_get(resolved.notebook_id)

        return _render_result(
            request,
            variant="success",
            title="Lote adicionado",
            message=f"{len(normalized)} fontes adicionadas com sucesso.",
            details={
                "notebook_id": resolved.notebook_id,
                "local_id": resolved.local_id,
                "source_ids": source_ids,
            },
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as exc:  # noqa: BLE001
        return _render_result(
            request,
            variant="error",
            title="Falha no lote de fontes",
            message=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=_elapsed_ms(started),
        )


@router.post("/web/jobs/audio", response_class=HTMLResponse)
async def web_create_audio_job(
    request: Request,
    notebook_id: str = Form(default=""),
    local_id: str = Form(default=""),
    name: str = Form(default=""),
    mode: str = Form(default=AudioSummaryMode.summary.value),
    language: str = Form(default="pt-BR"),
    duration: str = Form(default=AudioSummaryDuration.standard.value),
    focus_prompt: str = Form(default="Em quais aspectos os apresentadores de IA devem se concentrar nesse episodio?"),
) -> HTMLResponse:
    started = time.perf_counter()
    try:
        payload = GenerateAudioSummaryJobRequest(
            name=name or None,
            type="generate_audio_summary",
            notebook_id=notebook_id.strip() or None,
            local_id=int(local_id) if local_id.strip() else None,
            mode=AudioSummaryMode(mode),
            language=language,
            duration=AudioSummaryDuration(duration),
            focus_prompt=focus_prompt,
        )
        job = await request.app.state.job_service.submit_job(payload)
        return _render_result(
            request,
            variant="success",
            title="Job de audio criado",
            message="Processamento em background iniciado.",
            details={"job_id": job.id, "status": job.status.value, "notebook_id": job.notebook_id},
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as exc:  # noqa: BLE001
        return _render_result(
            request,
            variant="error",
            title="Falha ao criar job de audio",
            message=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=_elapsed_ms(started),
        )


@router.post("/web/jobs/video", response_class=HTMLResponse)
async def web_create_video_job(
    request: Request,
    notebook_id: str = Form(default=""),
    local_id: str = Form(default=""),
    name: str = Form(default=""),
    mode: str = Form(default=VideoSummaryMode.explanatory_video.value),
    style: str = Form(default=VideoSummaryStyle.summary.value),
    language: str = Form(default="pt-BR"),
    visual_style: str = Form(default="auto"),
    focus_prompt: str = Form(default="Em quais aspectos os apresentadores de IA devem se concentrar?"),
) -> HTMLResponse:
    started = time.perf_counter()
    try:
        payload = GenerateVideoSummaryJobRequest(
            name=name or None,
            type="generate_video_summary",
            notebook_id=notebook_id.strip() or None,
            local_id=int(local_id) if local_id.strip() else None,
            mode=VideoSummaryMode(mode),
            style=VideoSummaryStyle(style),
            language=language,
            visual_style=visual_style,
            focus_prompt=focus_prompt,
        )
        job = await request.app.state.job_service.submit_job(payload)
        return _render_result(
            request,
            variant="success",
            title="Job de video criado",
            message="Processamento em background iniciado.",
            details={"job_id": job.id, "status": job.status.value, "notebook_id": job.notebook_id},
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as exc:  # noqa: BLE001
        return _render_result(
            request,
            variant="error",
            title="Falha ao criar job de video",
            message=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=_elapsed_ms(started),
        )


@router.get("/web/jobs/search", response_class=HTMLResponse)
async def web_search_jobs(
    request: Request,
    job_id: str = "",
    name: str = "",
) -> HTMLResponse:
    jobs = request.app.state.job_service.list_jobs(job_id=job_id or None, name=name or None)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="partials/jobs_table.html",
        context={
            "request": request,
            "jobs": jobs,
        },
    )


def _render_result(
    request: Request,
    variant: str,
    title: str,
    message: str,
    details: dict[str, object] | None = None,
    elapsed_ms: int | None = None,
) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="partials/result_card.html",
        context={
            "request": request,
            "variant": variant,
            "title": title,
            "message": message,
            "details": details or {},
            "elapsed_ms": elapsed_ms,
        },
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
