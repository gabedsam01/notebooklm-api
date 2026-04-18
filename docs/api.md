# Referência Oficial da API REST e Modelos de Dados

Este documento detalha exaustivamente todos os endpoints, parâmetros, esquemas Pydantic e enumerações do projeto `notebooklm-api`.

> 💡 **Exemplos Práticos Disponíveis!**
> Para evitar suposições, documentamos scripts completos "Copiar e Colar" consumindo cada endpoint listado abaixo. Consulte:
> - 👉 [**Exemplos em `curl` (Terminal)**](../use-http-curl)
> - 👉 [**Exemplos em `Python` (Requests)**](../use-python)

Todas as requisições aguardam e enviam `application/json` codificado em UTF-8. A base path por padrão é `http://127.0.0.1:8080/`.

---

## 1. Módulo Health

### `GET /health`
Verifica a saúde e estado de inicialização.
- **Exemplos:** [curl](../use-http-curl/01-health.md) | [python](../use-python/01-health.py)
- **Resposta (`200 OK`)**:
  ```json
  {"status": "ok", "app": "notebooklm-api", "version": "..."}
  ```

---

## 2. Módulo Autenticação (`/auth`)

- **Exemplos Essenciais:** 
  - Status: [curl](../use-http-curl/02-auth-status.md)
  - Injetar Cookies: [curl](../use-http-curl/03-auth-storage-state.md)
  - Fluxo Interativo: [curl](../use-http-curl/04-auth-login-start.md) | [python](../use-python/02-auth.py)

### Modelos de Dados - Auth

#### `StorageCookie`
```json
{
  "name": "SID",          // string, required
  "value": "...",         // string, required
  "domain": ".google.com",// string, required
  "path": "/",            // string, default "/"
  "expires": 174000000,   // number | null (aceita 'expirationDate' e normaliza)
  "httpOnly": true,       // boolean | null
  "secure": true,         // boolean | null
  "sameSite": "Lax"       // enum: "Lax", "None", "Strict" | null
}
```

#### `StorageStatePayload`
```json
{
  "cookies": [ /* array de StorageCookie */ ],
  "origins": [ /* array de dicionários extras */ ]
}
```

#### `StorageStateSaveResponse` / `AuthStatusResponse`
Retornados por `POST /auth/storage-state` e `GET /auth/status`. Exibem a validade da conta.
Campos principais: `storage_state_present` (bool), `notebooklm_access_ok` (bool).

#### `LoginStartResponse` / `LoginCompleteRequest`
- **Start** retorna: `{"session_id": "str", "expires_at": "datetime"}`
- **Complete** recebe: `{"session_id": "str", "storage_state": StorageStatePayload}`

---

## 3. Módulo Notebooks (`/notebooks`)

- **Exemplos Essenciais:** 
  - CRUD & Sync: [curl](../use-http-curl/10-notebooks.md) | [python](../use-python/03-notebooks.py)

### Modelos de Dados - Notebooks

#### `NotebookTargetMixin` / Identificação Híbrida
Quase todas as operações de mutação requerem apontar um caderno. A API exige *ou* o UUID da nuvem ou o Auto-incremento SQLite:
```json
// Opção A
{ "notebook_id": "4b6c23f2-a05b-..." }
// Opção B
{ "local_id": 14 }
```

#### `NotebookCreateRequest`
```json
{ "title": "Anotações 2024" } // string min_length: 1, max_length: 200
```

#### `PersistedNotebook` (O modelo retornado em listagens)
```json
{
  "local_id": 1,
  "notebook_id": "google-uuid-xyz",
  "title": "Anotações 2024",
  "source_count": 0,
  "artifact_count": 0,
  "origin": "API",
  "metadata": {},
  "created_at": "2026-04-18T10:00:00Z",
  "updated_at": "2026-04-18T10:00:00Z"
}
```

### Endpoints 
- `POST /notebooks` -> Retorna `NotebookResponse`
- `GET /notebooks` -> Retorna `NotebookListResponse` (`count` e `items`)
- `POST /notebooks/sync` -> Retorna `NotebookSyncResponse`
- `GET /notebooks/{notebook_id}`
- `DELETE /notebooks/{notebook_id}`
- `DELETE /notebooks/local/{local_id}`

---

## 4. Módulo Sources (`/sources`)

- **Exemplos Essenciais:** [curl](../use-http-curl/20-sources.md) | [python](../use-python/04-sources.py)

### Modelos de Dados - Sources

#### `TextSourceInput`
```json
{
  "title": "Resumo Cap 1",       // max 200 chars
  "content": "A termodinâmica..." // max 120.000 chars
}
```

#### `AddBatchTextSourcesRequest`
```json
{
  "notebook_id": "xxxx",
  "sources": [ /* Array de até 100 TextSourceInput */ ]
}
```

---

## 5. Módulo Operations (`/operations`)

- **Exemplos Essenciais:** 
  - Áudio: [curl](../use-http-curl/40-operations-audio.md) | [python](../use-python/06-operations-audio.py)
  - Vídeo: [curl](../use-http-curl/41-operations-video.md) | [python](../use-python/07-operations-video.py)

### Enums de Operação
- **`AudioSummaryMode`**: `"summary"` (Padrão), `"detailed_analysis"`, `"critical_review"`, `"debate"`.
- **`AudioSummaryDuration`**: `"standard"` (Padrão), `"short"`.
- **`VideoSummaryMode`**: `"explanatory_video"`.
- **`VideoSummaryStyle`**: `"summary"`.

### Endpoints
*Nota: Aceitam Query Parameter opcional `?async=true` (Retorna 202 com Job ID) ou `?async=false` (Trava a requisição e retorna o Binário no final).*

#### `POST /operations/audio-summary`
**Payload (`AudioSummaryOperationRequest`):**
```json
{
  "notebook_id": "xxx", // ou local_id
  "mode": "summary",
  "language": "pt-BR", // max 20 chars
  "duration": "standard",
  "focus_prompt": "Fale apenas sobre as equações", // max 2.000 chars
  "name": "Nome Customizado do Job" // opcional
}
```

#### `POST /operations/video-summary`
**Payload (`VideoSummaryOperationRequest`):**
```json
{
  "notebook_id": "xxx",
  "mode": "explanatory_video",
  "style": "summary",
  "language": "pt-BR",
  "visual_style": "auto",
  "focus_prompt": "Foque no personagem principal",
  "name": "Nome Customizado"
}
```

---

## 6. Módulo Jobs (`/jobs`)

- **Exemplos Essenciais:** [curl](../use-http-curl/30-jobs.md) | [python](../use-python/05-jobs.py)

### Modelos de Dados - Jobs

#### `JobStatus` (Lifecycle Tracking)
`"queued"` -> `"running"` -> `"waiting_remote"` -> `"completed"` (ou `"failed"`, `"timed_out"`).

#### `JobRecord` (A Entidade JSON de acompanhamento)
```json
{
  "id": "e30e1f7c-7a6c-...",
  "name": "Meu Job",
  "type": "generate_audio_summary",
  "status": "completed",
  "input": { /* O Payload da request enviada */ },
  "result": { "artifact_reference": "reference_uuid", "media_type": "audio/wav" },
  "error": null,
  "created_at": "...",
  "started_at": "...",
  "completed_at": "...",
  "duration_ms": 14000,
  "notebook_id": "xxxx-xxxx-xxxx",
  "artifact_path": "data/artifacts/Resumo_Fisica.wav",
  "artifact_metadata": { 
     "file_name": "Resumo_Fisica.wav", 
     "content_type": "audio/wav", 
     "size_bytes": 10240, 
     "sha256": "..." 
  },
  "logs": [
    { "at": "...", "stage": "gerar_audio", "message": "Enviando comando..." }
  ]
}
```

### Endpoints
- `GET /jobs` -> Retorna lista filtrada via Query Params (`?job_id=`, `?name=`).
- `GET /jobs/{job_id}` -> Retorna o Status individual acima.

---

## 7. Módulo Artifacts (`/artifacts`)

- **Exemplos Essenciais:** [curl](../use-http-curl/50-artifacts.md) | [python](../use-python/08-artifacts.py)

### `GET /artifacts/{job_id}`
Realiza o fetch do arquivo estático nativo convertido (`.wav` ou `.mp4`).

**Status de Resposta Padrão:**
- `200 OK`: Binário anexado como `Content-Disposition: attachment`.
- `404 Not Found`: Arquivo do Job ID não existe fisicamente no Host ou Job UUID é inválido.
- `409 Conflict`: O Job existe no sistema, mas ainda está processando e não alcançou o status finalizado `completed`. Em requisições de Polling assíncrono, lide com 409 pausando a Thread de execução e retentando o download mais tarde.
