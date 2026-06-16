# NotebookLM API

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)
![Version](https://img.shields.io/badge/version-0.2.0-informational.svg)

API própria **HTTP-first** para operar fluxos do [NotebookLM do Google](https://notebooklm.google.com/) de forma programática — com **API REST (FastAPI)**, **CLI (`notebooklmapi`)** e uma **Web UI** server-rendered.

Internamente usa a biblioteca **[`notebooklm-py`](https://github.com/teng-lin/notebooklm-py)** como motor (`>=0.7.1,<0.8`), isolada atrás de um adapter próprio (`NotebookLMPyService`).

> ⚠️ **Não é uma API oficial do Google.** O NotebookLM não oferece API pública para este uso; a `notebooklm-py` usa endpoints internos que podem mudar/quebrar sem aviso. A autenticação depende de **sessão/cookies do Google** (`storage_state`), então trate tudo como **credencial sensível**. Veja [SECURITY.md](SECURITY.md).

---

## Arquitetura

| Componente | Papel |
|---|---|
| **FastAPI** (`app/main.py`, `app/api/`) | superfície HTTP (rotas REST) |
| **CLI** (`app/cli.py`, `notebooklmapi`) | gestão do processo (setup/start/off/status) + utilidades |
| **Web UI** (`app/web/`, Jinja2 + HTMX) | console server-rendered (atrás do Bearer) |
| **AccountRegistry** (`account_registry_service`) | contas em `data/accounts/`, status, paths internos |
| **NotebookLMPyService** (`notebooklm_service`) | adapter que encapsula a `notebooklm-py` |
| **JobService** (`job_service`) | operações assíncronas (áudio/vídeo), polling, download |
| **Artifacts** (`artifact_service`) | arquivos gerados, com scoping por conta |
| **Storage por conta** | `storage_state` isolado por `account_id` |

---

## Multi-conta

- Seleção por header **`X-NotebookLM-Account-Id: acc_xxx`** (ou query `?account_id=`); sem header, usa a conta **`default`**.
- Cada conta tem `storage_state` **isolado** e `status` próprio: `healthy`, `warming`, `degraded`, `challenge_required`, `expired`, `disabled`.
- **As respostas públicas de conta NÃO expõem caminhos internos** (sem `storage_state_path`/`chrome_profile_path`); usam booleans seguros (`has_storage_state`, `has_chrome_profile`, `enabled`).

Endpoints de conta: `POST/GET /accounts`, `GET /accounts/{id}`, `GET /accounts/{id}/status`, `POST /accounts/{id}/{bootstrap,verify,refresh,disable,enable}`.

---

## Segurança (resumo)

- **Autenticação Bearer, _default-deny_:** rotas sensíveis exigem `Authorization: Bearer $API_AUTH_TOKEN`. Sem token configurado e sem modo inseguro → **401** (não abre silenciosamente).
- **`ALLOW_INSECURE_NO_AUTH=true`** libera tudo — **apenas para dev local**, nunca em produção.
- **CORS fechado por padrão**; só libera origens listadas em `CORS_ALLOW_ORIGINS`. `allow_credentials` só vale com origem explícita (nunca com `*`).
- **`/health` é público.** **`/docs`, `/openapi.json`, `/redoc` são públicos** (decisão atual: expõem só o schema; sem segredos).
- **Web UI** fica **atrás do mesmo Bearer**. No browser ela só é usável em modo dev inseguro ou atrás de um proxy que injete o header `Authorization` (não há login/sessão próprios).
- Detalhes completos em **[SECURITY.md](SECURITY.md)**.

---

## Variáveis de ambiente

| Variável | Default | Descrição |
|---|---|---|
| `API_AUTH_TOKEN` | _(vazio)_ | Token Bearer das rotas sensíveis. **Obrigatório em produção.** Gere um valor forte. |
| `ALLOW_INSECURE_NO_AUTH` | `false` | `true` libera rotas sem token — **só dev local**. |
| `CORS_ALLOW_ORIGINS` | _(vazio)_ | CSV de origens permitidas. Vazio = CORS fechado. |
| `CORS_ALLOW_METHODS` | `GET,POST,PUT,PATCH,DELETE,OPTIONS` | Métodos CORS. |
| `CORS_ALLOW_HEADERS` | `Authorization,Content-Type,X-NotebookLM-Account-Id` | Headers CORS permitidos. |
| `CORS_ALLOW_CREDENTIALS` | `false` | Só `true` com origens explícitas (não `*`). |
| `NOTEBOOKLM_MODE` | `real` | `mock` (testes/dev) ou `real`. |
| `DATA_DIR`, `STORAGE_STATE_PATH`, … | `data/...` | Layout de dados (interno). |

> **`NOTEBOOKLM_HOME` não é usado pelo runtime do app** para isolar contas. O isolamento vem do `storage_state` explícito por conta passado à `notebooklm-py` (`from_storage(path)`). A dependência `notebooklm-py>=0.7.1,<0.8` está fixada no `pyproject.toml`.

---

## Executando

**Produção (com auth):**
```bash
export API_AUTH_TOKEN="$(openssl rand -hex 32)"   # nunca comite o valor
# CORS opcional: export CORS_ALLOW_ORIGINS="https://app.exemplo.com"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

**Dev local (sem token):**
```bash
export ALLOW_INSECURE_NO_AUTH=true   # NUNCA em produção
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

---

## Exemplos seguros

```bash
# /health é público
curl -s http://localhost:8080/health

# rota sensível: envie o Bearer (use a env var, não cole o token)
curl -s -H "Authorization: Bearer $API_AUTH_TOKEN" http://localhost:8080/accounts

# selecionar outra conta
curl -s -H "Authorization: Bearer $API_AUTH_TOKEN" \
     -H "X-NotebookLM-Account-Id: acc_xxx" http://localhost:8080/notebooks
```

> Nunca coloque o token, cookies ou `storage_state` reais em scripts versionados, logs ou prints.

---

## Erros (`ErrorResponse`)

Exceções da `notebooklm-py` e erros internos viram um **envelope seguro** com mensagem fixa por código (nunca o texto cru da exceção, sem stack trace nem segredos):

```json
{ "error": true, "code": "AUTH_REQUIRED", "message": "Autenticacao da conta expirada ou invalida; renove a sessao.", "detail": null }
```

Mapeamento (resumo): `NOT_FOUND` (404), `AUTH_REQUIRED` (401), `RATE_LIMITED` (429), `VALIDATION_ERROR` (422), `UPSTREAM_TIMEOUT` (504), `NOT_READY`/`FEATURE_UNAVAILABLE` (409), `QUOTA` (403), `UPSTREAM_SCHEMA_DRIFT`/`UPSTREAM_ERROR`/`UPSTREAM_NETWORK` (502), `INTERNAL_ERROR` (500). A falha de auth da API usa `401 {"detail": ...}`.

---

## Breaking changes 0.2.0

- **Auth obrigatória (default-deny):** rotas sensíveis exigem `Authorization: Bearer`, salvo `ALLOW_INSECURE_NO_AUTH=true`.
- **`AccountResponse` removeu `storage_state_path`, `chrome_profile_path` e `last_error`** (texto cru). Use `has_storage_state`, `has_chrome_profile`, `enabled`, `status`.
- **`jobs`/`artifacts` agora respeitam `account_id`:** acesso cross-conta retorna **404** (indistinguível de inexistente).
- **Erros da `notebooklm-py` viram envelope seguro** (sem exceção crua).
- **`NOTEBOOKLM_HOME` global e `global_env_lock` removidos** (isolamento por `storage_state` por conta).

Guia completo: **[docs/upgrade-0.2.md](docs/upgrade-0.2.md)** · histórico: **[CHANGELOG.md](CHANGELOG.md)** · smoke manual: **[docs/smoke-test.md](docs/smoke-test.md)**.

> Os arquivos em `docs/` (api/auth/cli/…) são anteriores à 0.2.0 e estão em revisão; em caso de divergência, prevalecem este README, o CHANGELOG e o guia de upgrade.

## License

MIT License. See [LICENSE](LICENSE).

