"""Wiring FastAPI dos handlers de excecao (envelope de erro seguro).

Registra handlers globais que convertem excecoes da notebooklm-py, o wrapper
NotebookLMOperationError e qualquer excecao inesperada em respostas
``ErrorResponse`` consistentes. Stack trace completo so vai para o log do
servidor; a resposta nunca o contem.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from notebooklm.exceptions import NotebookLMError

from app.services.exception_mapper import (
    map_exception_to_error_response,
    map_exception_to_http_status,
    sanitize_error_message,
)
from app.services.notebooklm_service import NotebookLMOperationError

logger = logging.getLogger(__name__)


async def _handle_known(request: Request, exc: Exception) -> JSONResponse:
    status_code = map_exception_to_http_status(exc)
    body = map_exception_to_error_response(exc)
    logger.warning(
        "Erro tratado em %s -> %s (%s)",
        request.url.path,
        body.code,
        sanitize_error_message(exc),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    # Loga o traceback completo apenas no servidor; resposta fica generica.
    logger.exception("Erro inesperado em %s", request.url.path)
    body = map_exception_to_error_response(exc)
    return JSONResponse(status_code=map_exception_to_http_status(exc), content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotebookLMError, _handle_known)
    app.add_exception_handler(NotebookLMOperationError, _handle_known)
    app.add_exception_handler(Exception, _handle_unexpected)
