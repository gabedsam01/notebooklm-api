# 02. Verificação de Status da Autenticação (`GET /auth/status`)

Verifica de forma cruzada se a sessão nativa salva no SQLite/disco da API tem validade com a Google Account.

### O Comando
```bash
curl -X GET "http://127.0.0.1:8080/auth/status"
```

### Respostas

**A. Conta Bloqueada ou Cookies Ausentes (`200 OK` mas com falha lógica):**
```json
{
  "storage_state_present": false,
  "storage_state_valid": false,
  "cookie_count": 0,
  "notebooklm_access_ok": false,
  "detail": "Nenhuma informacao de auth local"
}
```

**B. Autenticação Perfeita (Pronto para operar Mídias):**
```json
{
  "storage_state_present": true,
  "storage_state_valid": true,
  "cookie_count": 8,
  "notebooklm_access_ok": true,
  "detail": "Conta validada com sucesso"
}
```
