# Referência Oficial da API REST

Este documento detalha todos os endpoints, modelos e comportamentos disponíveis em `app/api/routes`.

Todas as requisições (exceto para `multipart/form-data`) esperam JSON em codificação padrão UTF-8 e enviam JSON como reposta, a menos que operem no modo `sync=false`, onde retornarão um binário (`audio/wav`, `video/mp4`). 

> **Aviso de Base URL:** Caso suba no default, a base path é `http://127.0.0.1:8080/`.

---

## 1. Módulo Health

### `GET /health`
Usado para verificação de liveness e status simples da API.
**Respostas Esperadas:**
- `200 OK`: `{"status": "ok", "app": "notebooklm-api", "version": "..."}`

---

## 2. Módulo Autenticação (`/auth`)

O módulo de autenticação salva, lê e verifica os cookies Playwright (`storage_state.json`) necessários para se disfarçar e operar requisições HTTP internas no NotebookLM do Google.

### `GET /auth/status`
Verifica se existe um estado de autenticação guardado no disco.
**Respostas Esperadas:**
- `200 OK`: 
```json
{
  "storage_state_present": true,
  "notebooklm_access_ok": true,
  "detail": null
}
```

### `POST /auth/storage-state`
Escreve o Cookie de forma limpa convertendo a lista para o formato em disco do arquivo de state.
**Payload:**
```json
{
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
}
```

### `POST /auth/login/start`
Inicia um fluxo assistido de login Playwright interativo, onde um usuário pode escanear o QR/inserir Senha. Isso emite um evento.

### `POST /auth/login/complete`
Finaliza o fluxo assistido caso bem sucedido e escreve o `storage_state.json`.

---

## 3. Módulo Notebooks (`/notebooks`)

Lida com os Notebooks e com o catálogo local em banco de dados SQLite. Notebooks podem ser chamados tanto via ID próprio do Google (`notebook_id`) como por atalho de chave primária relacional (`local_id`).

### `GET /notebooks`
Lista os notebooks salvos no Catálogo SQLite (`data/notebooks.db`).

### `POST /notebooks`
Cria de forma assíncrona o Notebook remoto e salva localmente.
**Payload:**
```json
{
  "title": "Novo Caderno de Física"
}
```

### `POST /notebooks/sync`
Bate na API Oficial do Google e faz a importação (`upsert`) dos notebooks da conta para a base SQLite local, removendo o que for orfão. Retorna `imported` e `deleted` count. Ele invoca internamente o `JobService.sync_notebook_artifacts()` para que artefatos anteriores já gerados no passado e perdidos se transformem em `JobRecords` completos.

### `GET /notebooks/{notebook_id}`
Atualiza o Notebook específico pegando os dados atuais e reescrevendo `source_count`.

### `DELETE /notebooks/{notebook_id}`
### `DELETE /notebooks/local/{local_id}`
Remove o Notebook remoto da conta e posteriormente limpa localmente da base SQLite caso bem sucedido.

---

## 4. Módulo Sources (`/sources`)

Envio de dados textuais crus para dentro do modelo para embasar o "caderno".

### `POST /sources/text`
Envia um texto cru em formato síncrono ou assíncrono.
**Payload:**
```json
{
  "notebook_id": "<id_uuid>",
  "title": "Resumo Cap 1",
  "content": "A termodinâmica..."
}
```

### `POST /sources/batch`
Envia múltiplos textos formatados. Cuidado com o Request Limit nativo do servidor/FastAPI para não gerar `HTTP 413 Payload Too Large`.

---

## 5. Módulo Operations (`/operations`)

Local principal para gerar Mídias usando a inteligência multimodal do Gemini inserida no NotebookLM.
Sempre informe `async=true` (Retorna 202 com Job Id) ou `async=false` (Trava requisição até o byte array do vídeo/áudio ser transferido nativamente na resposta HTTP).

### `POST /operations/audio-summary?async=true`
Pede que o painel multímodo de locutores discuta as fontes enviadas no Notebook.
**Payload (Modelo `GenerateAudioSummaryJobRequest`):**
```json
{
  "notebook_id": "<id_uuid>",
  "mode": "debate", 
  "language": "pt-BR",
  "duration": "standard", 
  "focus_prompt": "Fale apenas sobre as equações de maxwell"
}
```
**Campos do Enum:**
- `mode`: `summary`, `debate`, `detailed_analysis`, `critical_review`
- `duration`: `short`, `standard` 

### `POST /operations/video-summary?async=true`
Gerador nativo experimental (se disponível para sua conta Google) para clipes rápidos ou lousas virtuais explicando algo.
**Payload (Modelo `GenerateVideoSummaryJobRequest`):**
```json
{
  "notebook_id": "<id_uuid>",
  "mode": "explanatory_video",
  "style": "summary",
  "visual_style": "auto",
  "language": "pt-BR"
}
```

---

## 6. Módulo Jobs (`/jobs`)

Visualização e observabilidade das instâncias em execução background pelo sistema (criadas via Operations).

### `GET /jobs`
Lista todos os `JobRecords` contidos na pasta de persistência. Permite query params (ex: `?job_id=xxx&name=xxx`).

### `GET /jobs/{job_id}`
Mostra o status nativo. 
**Esquema `JobRecord`:**
```json
{
  "id": "e30e1f7c-7a6c-...",
  "type": "generate_audio_summary",
  "status": "completed",
  "notebook_id": "xxxxx-xxxx-xxxx",
  "started_at": "2026-04-18T10:00:00Z",
  "completed_at": "2026-04-18T10:04:12Z",
  "error": null,
  "artifact_path": "Meu_Novo_Documento.wav",
  "artifact_metadata": { "title": "Meu_Novo_Documento" },
  "logs": [
    { "at": "2026-04-18T10:00:01Z", "stage": "gerar_audio", "message": "Enviando comando..." },
    { "at": "2026-04-18T10:00:04Z", "stage": "waiting_remote", "message": "status remoto: RUNNING" }
  ],
  "result": { "artifact_reference": "reference_uuid", "media_type": "audio/wav" }
}
```

### Status do Enum `JobStatus`:
- `queued`: Não captado na memória da Thread
- `running`: Request inicial lançado
- `waiting_remote`: Backend comunicando, esperando artefato chegar 
- `completed`: Tudo certo
- `failed`: Exception interna na fila
- `timed_out`: Não processado por limite de timeout.

---

## 7. Módulo Artifacts (`/artifacts`)

Entrega de arquivos finalizados pelo Worker de Jobs.

### `GET /artifacts/{job_id}`
Realiza o fetch do arquivo estático nativo convertido. Baseado nos metadados salvos pelo job concluído.

**Status de Falha:**
- `404 Not Found`: Arquivo do Job ID não existe ou Job Request não existe.
- `409 Conflict`: O Job existe, mas ainda não se encontra em status finalizado para retornar nenhum binário.
