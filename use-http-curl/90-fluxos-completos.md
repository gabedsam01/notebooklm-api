# 90. Fluxos Completos Encapsulados (End-to-End)

Estes são exemplos de script Shell Script Linear completos simulando a orquestração que sua aplicação final faria em um cenário real. Todos eles pressupõe uma **conta previamente logada** (Storage State injetado) em estado "Saudável".

Para visualizar a mesma orquestração completa em Python, consulte a pasta `/use-python/90-end-to-end.py`.

## Fluxo A: Criar Caderno ➔ Adicionar Texto Síncrono ➔ Gerar Áudio Síncrono
O fluxo "Dumb" que tranca a thread, garantindo um áudio no final. É perigoso na vida real caso a conexão caia.

```bash
#!/bin/bash
set -e

# Passo 1: Criar o caderno (Usando JQ pra extrair a string sem aspas duplas "-r")
echo "Criando caderno..."
LOCAL_ID=$(curl -s -X POST "http://127.0.0.1:8080/notebooks" -H "Content-Type: application/json" -d '{"title": "Podcast Teste"}' | jq -r '.local_id')

echo "Caderno criado ID Local: $LOCAL_ID"

# Passo 2: Inserir a fonte
echo "Inserindo conteudo de texto..."
curl -s -X POST "http://127.0.0.1:8080/sources/text" -H "Content-Type: application/json" -d '{
  "local_id": '"$LOCAL_ID"',
  "title": "Materia Escolar",
  "content": "Estudo aprofundado sobre geologia."
}' > /dev/null

# Passo 3: Operar (Geração de Áudio Travando a Conexão)
echo "Pedindo o Áudio ao Google (Isto demorará cerca de 4 minutos)..."
curl -s -X POST "http://127.0.0.1:8080/operations/audio-summary?async=false" \
     -H "Content-Type: application/json" \
     -d '{
  "local_id": '"$LOCAL_ID"',
  "mode": "summary"
}' --output meu_resultado_final.wav

echo "WAV gerado com sucesso na sua máquina."
```

---

## Fluxo B: Tracking Assíncrono Perfeito com Extrator
O Fluxo corporativo recomendado. Extrai um Job assíncrono e bate na rota de Job Tracking até extrair `"completed"`, fazendo o parsing da resposta.

```bash
#!/bin/bash

# Digamos que o caderno e o source já existam na sua base
LOCAL_ID=1

# Passo 1: Start Asincrono
echo "Despachando ordem de video na fila de Jobs..."
JOB_ID=$(curl -s -X POST "http://127.0.0.1:8080/operations/video-summary?async=true" -H "Content-Type: application/json" -d '{
  "local_id": '"$LOCAL_ID"'
}' | jq -r '.job_id')

echo "Acompanhando o Job ID: $JOB_ID"

# Passo 2: O Polling Local
while true; do
  STATUS=$(curl -s -X GET "http://127.0.0.1:8080/jobs/$JOB_ID" | jq -r '.status')
  
  if [ "$STATUS" = "completed" ]; then
    echo "Job concluído no Servidor!"
    break
  elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "timed_out" ]; then
    echo "Falha crítica no Job: $STATUS."
    exit 1
  else
    echo "Status Atual: $STATUS. Aguardando 15 segundos..."
    sleep 15
  fi
done

# Passo 3: O Download Seguro (Pois já está completed)
echo "Baixando o mp4..."
curl -s -X GET "http://127.0.0.1:8080/artifacts/$JOB_ID" --output meu_video.mp4
echo "Pronto."
```
