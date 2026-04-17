# Docker guide

## Imagem e runtime

Arquivo base: `Dockerfile`

- base image: `python:3.12-slim`
- instala pacote via `pip install .`
- expoe porta `8080`
- declara volume persistente em `/app/data`
- comando padrao:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Build

```bash
docker build -t notebooklm-api:latest .
```

## Run (padrao)

```bash
docker run -d --name notebooklm-api \
  -p 8080:8080 \
  -v "$PWD/data:/app/data" \
  notebooklm-api:latest
```

## Run com variaveis de ambiente

Exemplo em modo mock:

```bash
docker run -d --name notebooklm-api \
  -p 8080:8080 \
  -v "$PWD/data:/app/data" \
  -e NOTEBOOKLM_MODE=mock \
  -e LOG_LEVEL=INFO \
  notebooklm-api:latest
```

## Persistencia de dados

Tudo que precisa sobreviver entre restarts deve ficar em `/app/data`:

- `notebooks.db`
- jobs JSON
- artefatos
- storage state
- PID/log (se usar CLI dentro do container)

Sem volume, esses dados se perdem ao recriar o container.

## Healthcheck manual

```bash
curl -s http://127.0.0.1:8080/health
```

Resposta esperada:

```json
{"status":"ok"}
```

## Logs e diagnostico

```bash
docker logs -f notebooklm-api
```

Para shell dentro do container:

```bash
docker exec -it notebooklm-api /bin/bash
```

## Atualizacao de imagem

Fluxo tipico:

1. build nova tag
2. parar/remover container antigo
3. subir novo container com mesmo volume

Exemplo:

```bash
docker stop notebooklm-api && docker rm notebooklm-api
docker build -t notebooklm-api:latest .
docker run -d --name notebooklm-api -p 8080:8080 -v "$PWD/data:/app/data" notebooklm-api:latest
```

## Notas para VPS e Dokploy

Em deploy gerenciado (Dokploy, Portainer, etc.):

- mapear porta externa -> `8080`
- montar volume persistente em `/app/data`
- definir env vars no painel (ex.: `NOTEBOOKLM_MODE`, `LOG_LEVEL`)
- configurar health check para `GET /health`

Para modo real:

- garantir `storage_state.json` valido dentro do volume
- proteger acesso da API com rede privada, firewall ou reverse proxy

## Boas praticas

- pin de tag de imagem em producao (evitar `latest` sem controle)
- backup regular do volume `data`
- permissao de escrita no host para `data/`
- monitorar crescimento de `data/artifacts` e `data/jobs`
