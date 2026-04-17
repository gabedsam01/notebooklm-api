# Troubleshooting

## 1) `notebooklmapi: command not found`

### Causa comum

- pacote nao instalado no ambiente atual
- `.venv` nao ativado

### Como resolver

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
notebooklmapi --help
```

Sem ativar venv:

```bash
.venv/bin/notebooklmapi --help
```

## 2) Virtualenv inconsistente

### Sintoma

- `setup` reclama de python/pip ausentes na `.venv`

### Como resolver

Recriar ambiente:

```bash
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -e .[dev]
```

## 3) API nao sobe na porta 8080

### Sintoma

- `notebooklmapi start` falha no health check
- `address already in use`

### Como resolver

1. verificar status:

```bash
notebooklmapi status
```

2. desligar instancia registrada:

```bash
notebooklmapi off
```

3. identificar processo ocupando 8080 (se necessario):

```bash
ss -ltnp | grep 8080
```

## 4) Auth pendente / sem acesso NotebookLM

### Sintoma

- `/auth/status` retorna `storage_state_present=false`
- ou `notebooklm_access_ok=false`

### Como resolver

1. reenviar storage state valido:

```bash
curl -X POST http://127.0.0.1:8080/auth/storage-state \
  -H "Content-Type: application/json" \
  -d '{"cookies":[{"name":"SID","value":"...","domain":".google.com","path":"/"}],"origins":[]}'
```

2. validar:

```bash
curl -s http://127.0.0.1:8080/auth/status
```

3. conferir se `NOTEBOOKLM_MODE` esta correto para o contexto

## 5) Modo real falha por dependencia nao oficial

### Sintoma

- erro relacionado a `notebooklm-py` nao encontrada

### Como resolver

- para desenvolvimento: usar `notebooklmapi start --dev`
- para modo real: instalar e validar biblioteca de integracao no ambiente

## 6) Operacao async sem artefato ainda disponivel

### Sintoma

- `GET /artifacts/{job_id}` retorna `409`

### Como resolver

- fazer polling em `GET /jobs/{job_id}`
- aguardar `status=completed`
- so entao baixar artefato

## 7) SQLite com estado inesperado

### Sintoma

- listagem local divergente da conta

### Como resolver

- rodar sync:

```bash
curl -X POST http://127.0.0.1:8080/notebooks/sync
```

ou

```bash
notebooklmapi list
```

Se necessario, fazer backup e resetar `data/notebooks.db` com cuidado.

## 8) Jobs falhando sem contexto

### Como diagnosticar

1. consultar job:

```bash
curl -s http://127.0.0.1:8080/jobs/<job_id>
```

2. verificar:

- `error`
- `logs[]` (stages)
- `input`

3. validar precondicoes:

- auth ok
- notebook existente
- notebook com fontes para gerar audio/video

## 9) Docker sem persistencia

### Sintoma

- dados somem ao recriar container

### Como resolver

Sempre montar volume:

```bash
docker run -d --name notebooklm-api -p 8080:8080 -v "$PWD/data:/app/data" notebooklm-api:latest
```

## 10) Permissao no volume Docker

### Sintoma

- falha para gravar `data/` (jobs, db, artifacts)

### Como resolver

- ajustar ownership/permissao no host para permitir escrita
- validar com `docker logs` e inspecionar erros de I/O

## 11) CLI `list` retorna erro mas mostra banco local

### Interpretacao

Comportamento esperado quando acesso remoto esta indisponivel:

- retorno code `1`
- resumo remoto como indisponivel
- dump do estado local ainda exibido

Isso permite diagnostico sem perder visibilidade do catalogo local.

## 12) Checklist rapido de recuperacao

1. `notebooklmapi status`
2. `curl /health`
3. `curl /auth/status`
4. `notebooklmapi list` (ou `/notebooks/sync`)
5. revisar logs de job e logs do processo
