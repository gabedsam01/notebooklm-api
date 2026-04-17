# API guide

## Base URL e transporte

- Base local padrao: `http://127.0.0.1:8080`
- Host/porta default da app: `0.0.0.0:8080`
- Healthcheck: `GET /health`
- OpenAPI interativo (FastAPI): `/docs`

## Content types

- Requisicoes JSON: `Content-Type: application/json`
- Requisicoes de UI web (form): `application/x-www-form-urlencoded` via HTMX
- Respostas JSON: `application/json`
- Respostas binarias:
  - audio: `audio/wav`
  - video: `video/mp4`

## Padroes de resposta

### Sucesso JSON

Resposta orientada a modelo Pydantic. Exemplo de job criado (`202`):

```json
{
  "id": "d112a0f30a734d7a9f63d0d2d9f7f0c0",
  "name": "generate_audio_summary-d112a0f3",
  "type": "generate_audio_summary",
  "status": "queued",
  "input": {
    "type": "generate_audio_summary",
    "notebook_id": "nb_123",
    "local_id": 12,
    "mode": "debate",
    "language": "pt-BR",
    "duration": "standard",
    "focus_prompt": "..."
  },
  "result": null,
  "error": null,
  "created_at": "2026-04-17T11:15:41.123456+00:00",
  "updated_at": "2026-04-17T11:15:41.123456+00:00",
  "logs": [
    {
      "at": "2026-04-17T11:15:41.123456+00:00",
      "stage": "queued",
      "message": "job enfileirado"
    }
  ]
}
```

### Erro JSON

Padrao FastAPI/HTTPException:

```json
{
  "detail": "mensagem de erro"
}
```

### Binario

Para operacoes sincronas (`async=false`) a API retorna `FileResponse` diretamente.

- audio: payload JSON -> bytes WAV
- video: payload JSON -> bytes MP4

## Status codes mais usados

- `200 OK`: leitura/mutacao concluida
- `201 Created`: notebook criado por `POST /notebooks`
- `202 Accepted`: job assinado em fila (`POST /jobs`, `POST /operations/*?async=true`)
- `400 Bad Request`: payload invalido em fluxos auth/login
- `404 Not Found`: job/notebook/artefato inexistente
- `409 Conflict`: acesso NotebookLM indisponivel, artefato ainda nao pronto
- `422 Unprocessable Entity`: validacao Pydantic falhou

## Rotas

### Health

- `GET /health`
  - resposta: `{ "status": "ok" }`

### Auth

- `GET /auth/status`
  - verifica se storage state existe e se acesso NotebookLM esta valido
- `POST /auth/storage-state`
  - salva cookies/storage state em arquivo local
- `POST /auth/login/start`
  - inicia sessao temporaria de login assistido
- `POST /auth/login/complete`
  - conclui login assistido com `session_id` + `storage_state`

### Notebooks

- `POST /notebooks`
  - cria notebook remoto e persiste no SQLite local
- `GET /notebooks`
  - lista notebooks persistidos localmente
- `POST /notebooks/sync`
  - sincroniza conta remota com SQLite (importa faltantes, remove orfaos)
- `GET /notebooks/{notebook_id}`
  - atualiza a partir do remoto quando possivel e retorna registro
- `DELETE /notebooks/{notebook_id}`
  - remove remoto + local (quando existirem)
- `DELETE /notebooks/local/{local_id}`
  - resolve `local_id` para `notebook_id` e remove

### Sources

- `POST /sources/text`
  - adiciona uma fonte textual
- `POST /sources/batch`
  - adiciona lote de fontes textuais

Ambos aceitam `notebook_id` ou `local_id` (pelo menos um).

### Jobs

- `POST /jobs`
  - cria job assincrono genrico (payload discriminado por `type`)
- `GET /jobs/{job_id}`
  - consulta estado de um job
- `GET /jobs?job_id=...&name=...`
  - lista/filtro de jobs

Tipos de job suportados:

- `create_notebook`
- `add_source`
- `add_sources_batch`
- `generate_audio_summary`
- `generate_video_summary`
- `delete_notebook`

### Operations (sync + async)

- `POST /operations/audio-summary?async=true|false`
- `POST /operations/video-summary?async=true|false`

Comportamento:

- `async=true` (default): retorna JSON do job (`202`)
- `async=false`: processa no request e retorna binario (`200`)

### Artifacts

- `GET /artifacts/{job_id}`
  - download do artefato associado ao job completo
  - retorna `409` se job ainda nao completou com artefato

## JSON vs binario: quando usar cada modo

### Modo assincrono (`async=true`)

Use quando voce precisa:

- fluxo resiliente para automacao
- polling de status
- recuperacao posterior de artefato
- observar logs e duracao no job

Fluxo:

1. `POST /operations/*?async=true`
2. Recebe `job_id`
3. Poll em `GET /jobs/{job_id}`
4. Download final em `GET /artifacts/{job_id}`

### Modo sincrono (`async=false`)

Use quando voce precisa:

- bytes imediatamente no mesmo request
- fluxo simples sem estado de job exposto

Atencao: o request pode demorar mais, pois inclui espera e download do artefato.

## Exemplos com curl

### 1) Health

```bash
curl -s http://127.0.0.1:8080/health
```

### 2) Importar storage state

```bash
curl -X POST http://127.0.0.1:8080/auth/storage-state \
  -H "Content-Type: application/json" \
  -d '{
    "cookies": [
      {
        "name": "SID",
        "value": "...",
        "domain": ".google.com",
        "path": "/",
        "httpOnly": true,
        "secure": true,
        "sameSite": "Lax"
      }
    ],
    "origins": []
  }'
```

### 3) Criar notebook

```bash
curl -X POST http://127.0.0.1:8080/notebooks \
  -H "Content-Type: application/json" \
  -d '{"title":"Notebook API"}'
```

### 4) Audio async (job)

```bash
curl -X POST "http://127.0.0.1:8080/operations/audio-summary?async=true" \
  -H "Content-Type: application/json" \
  -d '{
    "notebook_id": "<id>",
    "mode": "debate",
    "language": "pt-BR",
    "duration": "standard",
    "focus_prompt": "Pontos principais do episodio"
  }'
```

### 5) Poll job

```bash
curl -s http://127.0.0.1:8080/jobs/<job_id>
```

### 6) Download artefato do job

```bash
curl -L "http://127.0.0.1:8080/artifacts/<job_id>" --output audio.wav
```

### 7) Audio sync (binario)

```bash
curl -X POST "http://127.0.0.1:8080/operations/audio-summary?async=false" \
  -H "Content-Type: application/json" \
  -d '{
    "notebook_id": "<id>",
    "mode": "summary",
    "language": "pt-BR",
    "duration": "standard",
    "focus_prompt": "Resumo objetivo"
  }' \
  --output audio.wav
```

## Integracao n8n (referencia rapida)

Fluxo recomendado em n8n para geracao assincrona:

1. HTTP Request -> `POST /operations/audio-summary?async=true`
2. Loop/poll -> HTTP Request `GET /jobs/{job_id}`
3. IF -> `status == completed`
4. HTTP Request (download file) -> `GET /artifacts/{job_id}`

Dicas:

- para sync (`async=false`), configure node para tratar resposta como arquivo/binario
- para async, mantenha timeout baixo no node de criacao e faca polling separado
