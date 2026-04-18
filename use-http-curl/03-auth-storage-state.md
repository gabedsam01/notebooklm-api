# 03. Atualizar Estado via Extensão (Injeção via JSON)

Caso o servidor não possua UI visual para abrir a janela do Google, você fará login na sua máquina pessoal (com Google Chrome), usará uma extensão chamada *EditThisCookie*, copiará o Payload JSON e injetará manualmente via CURL na sua API Hospedada.

### O Comando (`POST /auth/storage-state`)
*Atenção aos headers `Content-Type: application/json` obrigatórios.*

```bash
curl -X POST "http://127.0.0.1:8080/auth/storage-state" \
     -H "Content-Type: application/json" \
     -d '{
  "cookies": [
    {
      "domain": ".google.com",
      "expirationDate": 1744158431.11,
      "hostOnly": false,
      "httpOnly": true,
      "name": "SID",
      "path": "/",
      "sameSite": "no_restriction",
      "secure": false,
      "session": false,
      "storeId": "0",
      "value": "g.a000nQjK1nLp_1_...",
      "id": 1
    },
    {
      "domain": ".google.com",
      "name": "HSID",
      "value": "AO...XX",
      "path": "/",
      "httpOnly": true,
      "secure": true
    }
  ]
}'
```

### Resposta JSON Esperada
Se o Google aceitar o conjunto que você enviou, você receberá a aprovação de que o ping interno validou o acesso.
```json
{
  "storage_state_present": true,
  "storage_state_valid": true,
  "cookie_count_received": 2,
  "cookie_count_kept": 2,
  "kept_cookie_names": ["SID", "HSID"],
  "has_minimum_auth_cookies": true,
  "notebooklm_access_ok": true,
  "detail": "Storage state salvo"
}
```
