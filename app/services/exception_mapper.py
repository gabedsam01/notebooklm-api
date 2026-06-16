"""Mapeamento puro excecao -> resposta HTTP segura (sem dependencia de FastAPI).

Traduz excecoes da notebooklm-py (e o wrapper NotebookLMOperationError do
adapter) em (status HTTP, code estavel, mensagem segura). Mensagens publicas
sao fixas por code -- nunca derivadas do texto cru da excecao -- para que
segredos/paths/traceback jamais cheguem ao cliente.
"""
from __future__ import annotations

from notebooklm.exceptions import (
    ArtifactFeatureUnavailableError,
    ArtifactNotReadyError,
    AuthError,
    ConfigurationError,
    DecodingError,
    NetworkError,
    NotebookLimitError,
    NotebookLMError,
    NotFoundError,
    RateLimitError,
    RPCError,
    RPCTimeoutError,
    ServerError,
    UnknownRPCMethodError,
    ValidationError,
    WaitTimeoutError,
)

from app.models.errors import ErrorResponse
from app.services.notebooklm_service import NotebookLMOperationError
from app.utils.error_sanitizer import sanitize_exception

# Ordem importa: do mais especifico para o mais generico (varias excecoes da
# lib usam heranca multipla com RPCError).
_MAPPING: list[tuple[tuple[type[BaseException], ...], int, str, str]] = [
    ((NotFoundError,), 404, "NOT_FOUND", "Recurso nao encontrado."),
    ((AuthError,), 401, "AUTH_REQUIRED", "Autenticacao da conta expirada ou invalida; renove a sessao."),
    ((RateLimitError,), 429, "RATE_LIMITED", "Limite de requisicoes atingido; tente novamente mais tarde."),
    ((ValidationError,), 422, "VALIDATION_ERROR", "Parametros invalidos."),
    ((WaitTimeoutError,), 504, "UPSTREAM_TIMEOUT", "A operacao no NotebookLM excedeu o tempo de espera."),
    ((ArtifactNotReadyError,), 409, "NOT_READY", "Artefato ainda nao esta pronto."),
    ((ArtifactFeatureUnavailableError,), 409, "FEATURE_UNAVAILABLE", "Recurso indisponivel para esta conta ou notebook."),
    ((NotebookLimitError,), 403, "QUOTA", "Limite ou quota da conta atingido."),
    ((UnknownRPCMethodError, DecodingError), 502, "UPSTREAM_SCHEMA_DRIFT", "O NotebookLM mudou o formato de resposta (schema drift)."),
    ((ServerError,), 502, "UPSTREAM_ERROR", "O NotebookLM retornou um erro de servidor."),
    ((NetworkError, RPCTimeoutError), 502, "UPSTREAM_NETWORK", "Falha de rede ao comunicar com o NotebookLM."),
    ((RPCError,), 502, "UPSTREAM_ERROR", "Falha na comunicacao com o NotebookLM."),
    ((ConfigurationError,), 500, "CONFIGURATION_ERROR", "Configuracao invalida do servidor."),
    ((NotebookLMError,), 502, "UPSTREAM_ERROR", "Falha na operacao do NotebookLM."),
]

_FALLBACK = (500, "INTERNAL_ERROR", "Erro interno inesperado.")
_OPERATION_FALLBACK = (502, "UPSTREAM_ERROR", "Falha na operacao do NotebookLM.")


def _resolve(exc: BaseException) -> tuple[int, str, str]:
    target = exc
    # NotebookLMOperationError costuma envolver a excecao real da lib via
    # `raise ... from exc`; preserva-se a especificidade desembrulhando a causa.
    if isinstance(exc, NotebookLMOperationError) and isinstance(exc.__cause__, NotebookLMError):
        target = exc.__cause__
    for types, status_code, code, message in _MAPPING:
        if isinstance(target, types):
            return status_code, code, message
    if isinstance(exc, NotebookLMOperationError):
        return _OPERATION_FALLBACK
    return _FALLBACK


def map_exception_to_http_status(exc: BaseException) -> int:
    return _resolve(exc)[0]


def map_exception_to_error_response(exc: BaseException) -> ErrorResponse:
    _, code, message = _resolve(exc)
    return ErrorResponse(code=code, message=message, detail=None)


def sanitize_error_message(exc: BaseException) -> str:
    """Mensagem sanitizada (para logs/estado interno); nunca para o envelope publico."""
    return sanitize_exception(exc)  # type: ignore[arg-type]
