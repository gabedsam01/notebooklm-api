# notebooklm-api

API independente para operar NotebookLM de forma programatica (HTTP-first), com CLI e UI web.

O projeto foi desenhado para automacoes (curl, n8n, scripts), com foco em:

- jobs assincronos com logs detalhados
- operacoes sincronas com retorno binario direto (audio/video)
- catalogo local de notebooks em SQLite
- modo real e modo mock para desenvolvimento/testes

## Features

- API FastAPI com rotas para auth, notebooks, fontes, jobs, operacoes e artefatos
- CLI `notebooklmapi` para setup, start/stop/status, list/sync e delete
- UI web server-rendered para operacao manual e debug
- persistencia local:
  - notebooks em `data/notebooks.db`
  - jobs em `data/jobs/*.json`
  - artefatos em `data/artifacts`
- suporte a `notebook_id` e `local_id` em endpoints-chave
- fluxo async (`202` + polling) e sync (arquivo binario no mesmo request)

## Arquitetura

Resumo dos blocos principais:

- `app/main.py`: bootstrap da app, DI via `app.state`, rotas e lifespan
- `app/api/routes/*`: endpoints HTTP
- `app/services/notebooklm_service.py`: adapter NotebookLM (`real`/`mock`)
- `app/services/notebook_catalog_service.py`: sincronizacao conta <-> SQLite
- `app/services/job_service.py`: fila local + execucao assincrona em thread
- `app/web/routes.py` + templates: UI web (Jinja2 + HTMX)

Modo de execucao:

- `NOTEBOOKLM_MODE=real` (padrao)
- `NOTEBOOKLM_MODE=mock` (dev/test)

## Instalacao

### Pre-requisitos

- Python `>=3.11`
- pip

### Como o comando `notebooklmapi` e instalado

O comando vem de `project.scripts` do `pyproject.toml` (`notebooklmapi = "app.cli:main"`).

Importante: diferente de npm global, ele nao vira um binario global automaticamente
so por existir no repositorio. Voce precisa instalar o pacote em algum ambiente Python
(venv, pipx, etc.).

### Modo 1 (recomendado): venv ativado

```bash
cd ~/Documentos/notebooklm-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

notebooklmapi setup
notebooklmapi start
```

### Modo 2: sem ativar venv

```bash
cd ~/Documentos/notebooklm-api
python3 -m venv .venv
.venv/bin/pip install -e .[dev]

.venv/bin/notebooklmapi setup
.venv/bin/notebooklmapi start
```

### Modo 3: instalacao global isolada com pipx

```bash
cd ~/Documentos/notebooklm-api
pipx install .
```

## Configuracao (`.env`)

Base recomendada: copiar de `.env.example`.

Variaveis principais:

- `APP_HOST` (default `0.0.0.0`)
- `APP_PORT` (default `8080`)
- `NOTEBOOKLM_MODE` (`real` ou `mock`, default `real`)
- `DATA_DIR` (default `data`)
- `SQLITE_DB_PATH` (default `data/notebooks.db`)
- `STORAGE_STATE_PATH` (default `data/auth/storage_state.json`)

Timeouts (artefatos longos):

- `ARTIFACT_WAIT_TIMEOUT_SECONDS` (default `1800` - 30 min)
- `ARTIFACT_POLL_INTERVAL_SECONDS` (default `15.0`)
- `AUDIO_WAIT_TIMEOUT_SECONDS` (opcional, sobrescreve `ARTIFACT_WAIT_TIMEOUT_SECONDS` para audio)
- `VIDEO_WAIT_TIMEOUT_SECONDS` (opcional, sobrescreve `ARTIFACT_WAIT_TIMEOUT_SECONDS` para video)

Observacao: `NOTEBOOKLM_STORAGE_STATE_PATH` e aceito como alias legado.

## Uso CLI

Comandos principais:

- `notebooklmapi setup`
- `notebooklmapi start`
- `notebooklmapi start --dev`
- `notebooklmapi off`
- `notebooklmapi status`
- `notebooklmapi list`
- `notebooklmapi list --dev`
- `notebooklmapi delete <notebook_id>`

### O que cada comando faz

#### `setup`

- cria `.venv` se necessario
- instala deps (`-e .[dev]`)
- cria `.env` se faltar
- prepara diretorios e valida boot

#### `start`

- sobe API em background em `0.0.0.0:8080`
- grava PID em `data/run/notebooklmapi.pid`
- grava logs em `data/run/notebooklmapi.log`

#### `start --dev`

- igual ao `start`, mas forcando `NOTEBOOKLM_MODE=mock`

#### `off`

- encerra processo por PID file (SIGTERM, fallback SIGKILL)

#### `status`

- informa online/offline, PID e log file

#### `list` / `list --dev`

- sincroniza conta remota com SQLite local
- imprime:
  - encontrados no Google
  - encontrados no banco
  - adicionados
  - removidos
- em indisponibilidade remota, ainda mostra estado local

#### `delete <notebook_id>`

- tenta remover remoto
- remove local se existir
- mostra `deleted_remote`, `deleted_local`, `detail`

## Uso API

Base URL local: `http://127.0.0.1:8080`

### Rotas principais

- health:
  - `GET /health`
- auth:
  - `GET /auth/status`
  - `POST /auth/storage-state`
  - `POST /auth/login/start`
  - `POST /auth/login/complete`
- notebooks:
  - `POST /notebooks`
  - `GET /notebooks`
  - `POST /notebooks/sync`
  - `GET /notebooks/{notebook_id}`
  - `DELETE /notebooks/{notebook_id}`
  - `DELETE /notebooks/local/{local_id}`
- sources:
  - `POST /sources/text`
  - `POST /sources/batch`
- jobs:
  - `POST /jobs`
  - `GET /jobs/{job_id}`
  - `GET /jobs?job_id=...&name=...`
- operacoes:
  - `POST /operations/audio-summary?async=true|false`
  - `POST /operations/video-summary?async=true|false`
- artefatos:
  - `GET /artifacts/{job_id}`

### Payloads e respostas

- requests em JSON: `Content-Type: application/json`
- respostas de sucesso:
  - JSON em endpoints de dados/jobs
  - binario (`audio/wav`, `video/mp4`) em operacoes sync
- erros: padrao `{"detail":"..."}`

Status codes comuns:

- `200`, `201`, `202`, `400`, `404`, `409`, `422`

### Async vs sync

#### Async (`async=true`, default)

1. cria job (`202`)
2. consulta status em `/jobs/{job_id}`
3. baixa arquivo em `/artifacts/{job_id}`

#### Sync (`async=false`)

- a chamada bloqueia ate gerar/baixar artefato
- retorno e arquivo binario direto

### Exemplo curl: importar storage state

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

### Exemplo curl: audio async

```bash
curl -X POST "http://127.0.0.1:8080/operations/audio-summary?async=true" \
  -H "Content-Type: application/json" \
  -d '{
    "notebook_id": "<id>",
    "mode": "debate",
    "language": "pt-BR",
    "duration": "standard",
    "focus_prompt": "Pontos principais"
  }'
```

### Exemplo curl: audio sync (arquivo direto)

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

### Exemplo n8n (fluxo recomendado)

1. HTTP Request -> `POST /operations/audio-summary?async=true`
2. loop de polling -> `GET /jobs/{job_id}`
3. condicao `status == completed`
4. HTTP Request (download file) -> `GET /artifacts/{job_id}`

## Uso UI

Abra `http://127.0.0.1:8080/`.

A UI oferece:

- import de storage state
- criacao/sync/delecao de notebooks
- envio de fontes (unica/lote)
- criacao de job de audio/video
- tabela de jobs com logs e resultado
- download de artefatos

Atualizacao automatica:

- notebooks: a cada 5s
- jobs: a cada 3s

## SQLite

Banco local: `data/notebooks.db`.

Campos persistidos do notebook:

- `id` (`local_id`)
- `notebook_id`
- `title`
- `source_count`
- `artifact_count`
- `origin`
- `metadata_json`
- `created_at`
- `updated_at`

Sincronizacao conta <-> banco:

- importa notebooks remotos faltantes
- remove locais orfaos

## Auth NotebookLM

Modo `real` depende de storage state com cookies validos.

Checklist:

1. `POST /auth/storage-state`
2. `GET /auth/status`
3. confirmar `storage_state_present=true` e `notebooklm_access_ok=true`

Notas importantes:

- integracao real usa biblioteca nao oficial (`notebooklm-py`)
- `storage_state.json` deve ser tratado como segredo
- arquivo e salvo com permissao restrita (`0600`)

## Docker

### Build

```bash
docker build -t notebooklm-api:latest .
```

### Run

```bash
docker run -d --name notebooklm-api \
  -p 8080:8080 \
  -v "$PWD/data:/app/data" \
  notebooklm-api:latest
```

### Run em mock

```bash
docker run -d --name notebooklm-api \
  -p 8080:8080 \
  -v "$PWD/data:/app/data" \
  -e NOTEBOOKLM_MODE=mock \
  notebooklm-api:latest
```

### Stop

```bash
docker stop notebooklm-api
docker rm notebooklm-api
```

## Testes

Com venv:

```bash
.venv/bin/python -m pytest
```

Cobertura atual inclui:

- health e home
- auth (storage-state e login assistido)
- persistencia SQLite de notebooks
- sync import/remove entre conta e banco
- sources unica/lote com `notebook_id` ou `local_id`
- operacoes async e sync (audio/video)
- fluxo de delecao remoto/local
- comportamento de CLI (`start --dev`, `list`, status/off)

## Troubleshooting (resumo)

Problemas comuns:

- `command not found` para `notebooklmapi`
- venv quebrada/inconsistente
- auth pendente ou sessao invalida
- porta 8080 ocupada
- `409` ao baixar artefato antes do job concluir
- volume Docker sem persistencia/permissao

Guia completo: `docs/troubleshooting.md`.

## Roadmap

- melhorar observabilidade (metricas e tracing)
- opcao de worker externo/distribuido para jobs
- politicas de limpeza/retencao para `data/jobs` e `data/artifacts`
- melhorias de seguranca operacional (hardening para deploy publico)
- evoluir compatibilidade com integracoes NotebookLM reais

## Documentacao detalhada

- `docs/index.md`
- `docs/api.md`
- `docs/cli.md`
- `docs/auth.md`
- `docs/jobs.md`
- `docs/notebooks.md`
- `docs/ui.md`
- `docs/docker.md`
- `docs/troubleshooting.md`
