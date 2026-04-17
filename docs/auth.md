# Auth guide

## Contexto

Este projeto nao usa OAuth oficial do Google para NotebookLM.

A autenticacao em modo `real` depende de um arquivo de storage state
(cookies + origins), normalmente exportado de um browser autenticado.

Arquivo padrao:

- `data/auth/storage_state.json`

## Componentes envolvidos

- modelo: `app/models/auth.py`
- servico de persistencia: `app/services/storage_state_service.py`
- servico de auth: `app/services/notebooklm_auth_service.py`
- rotas: `app/api/routes/auth.py`

## Rotas de autenticacao

### `GET /auth/status`

Retorna:

- `storage_state_present`: se arquivo existe e nao esta vazio
- `storage_state_valid`: se o arquivo JSON foi parseado com sucesso
- `cookie_count`: total de cookies carregados
- `notebooklm_access_ok`: se o backend NotebookLM validou acesso
- `detail`: mensagem operacional

Exemplo:

```json
{
  "storage_state_present": true,
  "storage_state_valid": true,
  "cookie_count": 22,
  "notebooklm_access_ok": false,
  "detail": "Storage state salvo (22 cookies), mas acesso real ainda nao validado. Erro original: ..."
}
```

### `POST /auth/storage-state`

Salva storage state diretamente.

Payload pode ser o objeto completo (formato Playwright):

```json
{
  "cookies": [
    {
      "name": "SID",
      "value": "...",
      "domain": ".google.com",
      "path": "/"
    }
  ],
  "origins": []
}
```

Ou simplesmente um array bruto de cookies, que sera convertido automaticamente:

```json
[
  {
    "name": "SID",
    "value": "...",
    "domain": ".google.com",
    "path": "/"
  }
]
```

Resposta:

```json
{
  "saved": true,
  "detail": "Storage state salvo com sucesso."
}
```

### `POST /auth/login/start`

Inicia um fluxo assistido simples:

- gera `session_id`
- define expiracao (TTL padrao: 20 minutos)
- guarda sessao apenas em memoria do processo

Resposta:

```json
{
  "session_id": "abc123...",
  "expires_at": "2026-04-17T13:00:00+00:00",
  "detail": "Fluxo assistido iniciado..."
}
```

### `POST /auth/login/complete`

Conclui o fluxo assistido com:

- `session_id`
- `storage_state`

Se sessao expirou/nao existe, retorna `400` com `detail`.

## Fluxo recomendado (modo real)

1. iniciar API: `notebooklmapi start`
2. enviar cookies em `POST /auth/storage-state`
3. validar com `GET /auth/status`
4. somente depois executar operacoes em `/notebooks`, `/sources`, `/operations`

## Fluxo assistido alternativo

1. `POST /auth/login/start`
2. autenticar manualmente no browser e capturar storage state
3. `POST /auth/login/complete` com `session_id` retornado
4. `GET /auth/status` para confirmar acesso

## Limitacoes reais (importante)

- nao existe API publica oficial do NotebookLM para esse fluxo
- integracao `real` usa biblioteca nao oficial (`notebooklm-py`)
- mudancas externas no NotebookLM podem quebrar compatibilidade
- `session_id` do fluxo assistido e volatil (memoria), reiniciar processo invalida sessoes pendentes

## Seguranca

### Permissoes de arquivo

O `StorageStateService` grava arquivo com permissao `0600`:

- arquivo temporario `.tmp` com `chmod 600`
- replace atomico para o destino final
- `chmod 600` novamente no destino

### Boas praticas

- nunca commitar `data/auth/storage_state.json`
- manter `data/` fora de backups publicos
- em Docker/VPS, usar volume privado com permissao restrita
- rotacionar cookies/sessoes em caso de suspeita de vazamento

### Sinais de risco

- `notebooklm_access_ok=false` repetidamente
- falhas de validacao apos troca de conta/browser
- arquivo de storage state vazio ou corrompido

## Troubleshooting rapido

- `Storage state ausente`: envie payload novamente em `/auth/storage-state`
- `Falha ao validar sessao notebooklm-py`: revisar cookies, modo e dependencia real
- `400` em `/auth/login/complete`: sessao expirada ou `session_id` invalido

Para mais casos, veja `docs/troubleshooting.md`.
