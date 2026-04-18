# Jobs guide

## Visao geral

Jobs sao a base do fluxo assincrono da API.

- endpoint principal: `POST /jobs`
- endpoint de consulta: `GET /jobs/{job_id}`
- endpoint de listagem/filtro: `GET /jobs?job_id=...&name=...`
- download final de artefato: `GET /artifacts/{job_id}`

Persistencia local:

- metadados/jobs: `data/jobs/<job_id>.json`
- artefatos: `data/artifacts/<job_id>.<ext>`
- payload temporario de execucao: `data/tmp/<job_id>/input.json` (removido ao final)

## Modelo de job

Campos principais (`JobRecord`):

- `id`, `name`, `type`, `status`
- `input`: payload normalizado
- `result`: saida de negocio (quando concluido)
- `error`: erro sanitizado (quando falha)
- `created_at`, `started_at`, `completed_at`, `updated_at`, `duration_ms`
- `notebook_id`
- `artifact_path`, `artifact_metadata`
- `logs`: trilha de etapas (`stage`, `message`, `at`)

## Status de job

- `queued`: enfileirado
- `running`: em execucao local
- `waiting_remote`: aguardando processamento remoto no NotebookLM (comum em audio/video)
- `completed`: concluido com sucesso
- `failed`: falhou por erro interno ou de rede
- `timed_out`: excedeu o timeout configurado de espera remota

## Tipos de job

- `create_notebook`
- `add_source`
- `add_sources_batch`
- `generate_audio_summary`
- `generate_video_summary`
- `delete_notebook`

## Fluxo assincrono padrao

1. cliente envia `POST /jobs` (ou `POST /operations/*?async=true`)
2. API retorna `202` com `job_id`
3. worker local executa em thread daemon
4. cliente faz polling em `GET /jobs/{job_id}`
5. quando `status=completed`, cliente baixa arquivo via `GET /artifacts/{job_id}` (se houver artefato)

## Exemplo: criar job de audio

```bash
curl -X POST http://127.0.0.1:8080/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "generate_audio_summary",
    "name": "audio-episodio-42",
    "notebook_id": "<id>",
    "mode": "debate",
    "language": "pt-BR",
    "duration": "standard",
    "focus_prompt": "Pontos principais"
  }'
```

## Polling recomendado

Estrutura simples de polling:

1. aguardar 1-2s entre requests
2. parar quando `status` for `completed` ou `failed`
3. em `failed`, registrar `error` + `logs`
4. em `completed` com `artifact_path`, baixar via `/artifacts/{job_id}`

Exemplo:

```bash
curl -s http://127.0.0.1:8080/jobs/<job_id>
```

## Logs e debug

Cada job acumula eventos em `logs[]` com estagios como:

- `queued`
- `running`
- `creating_notebook`
- `adding_source`
- `adding_sources_batch`
- `generate_audio`
- `download_audio`
- `generate_video`
- `download_video`
- `deleting_notebook`
- `failed`
- `cleanup`

Esses logs aparecem:

- no JSON do job (`GET /jobs/{job_id}`)
- na UI web na tabela de jobs (detalhes expansivos)

## Artefatos

Para jobs de audio/video:

- `artifact_path` guarda caminho relativo a `data/` (ex.: `artifacts/<job_id>.wav`)
- `artifact_metadata` inclui:
  - `file_name`
  - `content_type`
  - `size_bytes`
  - `sha256`

Download:

```bash
curl -L http://127.0.0.1:8080/artifacts/<job_id> --output out.bin
```

Retornos comuns em `/artifacts/{job_id}`:

- `200`: arquivo entregue
- `404`: job nao encontrado ou arquivo ausente
- `409`: job ainda nao concluiu com artefato

## Limpeza e ciclo de vida

- durante execucao, o payload de entrada e salvo em `data/tmp/<job_id>/input.json`
- ao final (sucesso ou falha), a pasta temporaria do job e removida
- os arquivos de `data/jobs` e `data/artifacts` permanecem para auditoria/debug

## Fluxo sync vs async

Mesmo em operacoes sincronas (`/operations/*?async=false`), o pipeline interno de geracao/download e semelhante,
mas sem persistir `JobRecord` para o cliente.

Use async quando precisar:

- historico
- observabilidade
- retry orchestration
- integracao com n8n/filas

## Diagnostico rapido

Se um job falhar:

1. leia `error`
2. inspecione `logs` por estagio
3. confirme auth (`GET /auth/status`)
4. valide se notebook tem fontes
5. confira se `data/artifacts` e gravavel

Mais casos em `docs/troubleshooting.md`.
