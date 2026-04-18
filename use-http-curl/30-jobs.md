# 30. Fila e Acompanhamento de Jobs (Jobs)

A API armazena as operações longas localmente na pasta `data/jobs/`. Estes endpoints servem apenas de modo Leitura para investigar e acompanhar o estado dos `operations`.

## A. Listagem Geral de Jobs
Se você deseja saber quais áudios foram gerados hoje ou no passado.

### `GET /jobs`
```bash
# Busca irrestrita (Limita por padrao a 100 jobs dos mais novos para velhos)
curl -X GET "http://127.0.0.1:8080/jobs"
```
**Buscas parametrizadas com Filtros**:
```bash
# Somente videos e somente de um caderno especifico
curl -X GET "http://127.0.0.1:8080/jobs?notebook_id=xxx&type=generate_video_summary"
```

---

## B. Acompanhando Status em Tempo Real
Este é o endpoint feito para se usar em *Polling* (Um *While True* rodando na sua aplicação a cada X segundos). O `status` transitará por `queued`, `running`, `waiting_remote` até chegar em `completed`.

### `GET /jobs/{job_id}`
```bash
curl -X GET "http://127.0.0.1:8080/jobs/e30e1f7c-7a6c-482c-9d6a-..."
```

**Exemplo de Resposta do JSON**:
Se você reparar no array `"logs"`, os Workers da sua API informam com precisão cada evento que acontece nas camadas de comunicação durante aqueles tortuosos minutos sem resposta, permitindo criar barras de loading fiéis.
```json
{
  "id": "e30e1f7c-...",
  "name": "Meu Resumo",
  "type": "generate_audio_summary",
  "status": "completed",
  "input": {
    "notebook_id": "f83b2a-...",
    "mode": "summary",
    "language": "pt-BR",
    "duration": "standard"
  },
  "result": {
    "artifact_reference": "reference_uuid",
    "media_type": "audio/wav"
  },
  "error": null,
  "created_at": "2026-04-18T10:00:00.000Z",
  "started_at": "2026-04-18T10:00:01.000Z",
  "completed_at": "2026-04-18T10:04:12.000Z",
  "duration_ms": 251000,
  "notebook_id": "f83b2a-...",
  "artifact_path": "data/artifacts/Meu_Resumo.wav",
  "artifact_metadata": {
    "file_name": "Meu_Resumo.wav",
    "content_type": "audio/wav",
    "size_bytes": 1048576,
    "sha256": "abcdef..."
  },
  "logs": [
    {
      "at": "2026-04-18T10:00:01.000Z",
      "stage": "gerar_audio",
      "message": "Enviando comando de resumo de audio..."
    },
    {
      "at": "2026-04-18T10:00:04.000Z",
      "stage": "waiting_remote",
      "message": "status remoto recebido do servidor: RUNNING"
    },
    {
      "at": "2026-04-18T10:01:04.000Z",
      "stage": "waiting_remote",
      "message": "status remoto recebido do servidor: GENERATING_AUDIO"
    },
    {
      "at": "2026-04-18T10:04:10.000Z",
      "stage": "download",
      "message": "Artefato detectado na nuvem. Baixando em background..."
    }
  ]
}
```
