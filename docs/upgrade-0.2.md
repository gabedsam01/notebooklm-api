# Upgrade para a 0.2.0

A 0.2.0 traz **breaking changes** (auth, contrato de conta, scoping, erros). Leia antes de atualizar.

## 1. Dependências

```bash
# instale/atualize com o pin novo (pyproject ja fixa notebooklm-py>=0.7.1,<0.8)
pip install -e ".[dev]"
# confirme
python -c "import importlib.metadata as m; print('notebooklm-py', m.version('notebooklm-py'))"
```

## 2. Configurar `API_AUTH_TOKEN`

A API agora é **default-deny**. Em produção, configure um token forte:

```bash
export API_AUTH_TOKEN="$(openssl rand -hex 32)"   # nunca comite o valor real
```

Sem `API_AUTH_TOKEN` e sem `ALLOW_INSECURE_NO_AUTH=true`, as rotas sensíveis retornam **401**.

## 3. Ajustar clientes (curl / n8n / SDKs) para enviar `Authorization`

Adicione o header em **todas** as rotas sensíveis (tudo exceto `/health`, `/docs`, `/openapi.json`):

```bash
curl -H "Authorization: Bearer $API_AUTH_TOKEN" http://localhost:8080/accounts
```

- **n8n / HTTP Request node:** adicione um header `Authorization` = `Bearer <seu-token>` (use credencial, não texto fixo).
- Mantenha o `X-NotebookLM-Account-Id` para selecionar conta (continua funcionando).

## 4. Consumidores que liam paths/`last_error`

`AccountResponse` **não retorna mais** `storage_state_path`, `chrome_profile_path` nem `last_error` textual. Migre:

| Antes (removido) | Agora (use) |
|---|---|
| `storage_state_path` | `has_storage_state` (bool) |
| `chrome_profile_path` | `has_chrome_profile` (bool) |
| `last_error` (texto) | `status` (categoria) + logs do servidor |
| _(novo)_ | `enabled` (bool) |

## 5. 404 cross-conta

`GET /jobs/{id}` e `GET /artifacts/{id}` agora exigem a **conta corrente** (header). Acesso a um job/artefato de outra conta retorna **404** (igual a inexistente). Garanta que o cliente envie o `X-NotebookLM-Account-Id` correto.

## 6. Interpretar `ErrorResponse`

Erros internos/upstream vêm como:

```json
{ "error": true, "code": "RATE_LIMITED", "message": "Limite de requisicoes atingido; tente novamente mais tarde.", "detail": null }
```

Trate por `code` (estável). Falha de **auth da API** vem como `401 {"detail": "Autenticacao necessaria."}`.

## 7. Modo dev inseguro

```bash
export ALLOW_INSECURE_NO_AUTH=true   # SOMENTE local; libera rotas e a Web UI no browser
```

## 8. Rollback

Se algo der errado:

1. **Faça backup de `data/` antes do upgrade** (`cp -a data data.bak`).
2. Volte para o commit/tag anterior:
   ```bash
   git checkout v0.1.0     # ou o commit anterior
   pip install -e ".[dev]"
   ```
3. Em **dev**, se quiser reabrir rotas sem token, use `ALLOW_INSECURE_NO_AUTH=true` (nunca em produção).
4. **Não apague `data/`** — os dados (contas, SQLite, artefatos) são compatíveis entre 0.1.0 e 0.2.0.
