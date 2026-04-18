# 41. Operações com Vídeo (Lousa / Clipes)

Endpoint experimental nativo para geração em vídeo daquele caderno. Segue exatamente a mesma arquitetura de Síncrono e Assíncrono que operamos no Áudio.

## A. O Modo Assíncrono (`?async=true`) Recomendado
Dispara na Fila Interna (Job) liberando o client imediatamente.

### `POST /operations/video-summary`
```bash
curl -X POST "http://127.0.0.1:8080/operations/video-summary?async=true" \
     -H "Content-Type: application/json" \
     -d '{
  "local_id": 1,
  "mode": "explanatory_video",
  "style": "summary",
  "visual_style": "auto",
  "language": "pt-BR",
  "focus_prompt": "Foque apenas nas palavras-chave no video."
}'
```

**Resposta HTTP 202 (Accepted)**:
```json
{
  "job_id": "b18b44ff-...",
  "detail": "Operacao iniciada de forma assincrona."
}
```

---

## B. O Modo Síncrono / Imediatista (`?async=false`)
Abaixa a mídia como Output Buffer binário final.

> A opção `--output` intercepta o binário recebido no Terminal Linux/Mac e escreve no File System para ele não crachar a janela.

### `POST /operations/video-summary`
```bash
curl -X POST "http://127.0.0.1:8080/operations/video-summary?async=false" \
     -H "Content-Type: application/json" \
     -d '{
  "local_id": 1,
  "mode": "explanatory_video",
  "language": "pt-BR"
}' --output explicacao_em_lousa.mp4
```

**Resultado:** Seu terminal criará um `.mp4` real contendo o clip gerado pela Google Cloud após a conclusão demorada do Request.
