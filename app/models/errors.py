from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Envelope de erro estavel e seguro para respostas HTTP.

    Nunca inclui stack trace, cookies, storage_state, headers sensiveis ou
    paths internos. ``code`` e um identificador estavel; ``message`` e uma
    frase curta e segura; ``detail`` fica reservado para informacao adicional
    ja sanitizada (por padrao ``None``).
    """

    error: bool = True
    code: str
    message: str
    detail: str | None = None
