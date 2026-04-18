# 01. Health Check (`GET /health`)

Garante que o backend da API está vivo, no ar e ouvindo requisições HTTP corretamente. Não bate no Google.

### O Comando
```bash
curl -X GET "http://127.0.0.1:8080/health"
```

### Resposta JSON Esperada (`200 OK`)
```json
{
  "status": "ok",
  "app": "notebooklm-api",
  "version": "1.0.0"
}
```
