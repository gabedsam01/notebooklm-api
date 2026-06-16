# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/) e [SemVer](https://semver.org/).

## [0.2.0] - 2026-06-16

Migração da `notebooklm-py` para `>=0.7.1,<0.8` e endurecimento de segurança
(Ondas 1–7). Veja o guia: [docs/upgrade-0.2.md](docs/upgrade-0.2.md).

### Changed
- `notebooklm-py>=0.7.1,<0.8` (antes `>=0.3.4` sem teto).
- Adapter compatível com `Artifact.kind` (substitui `artifact_type` removido na lib).
- `NotebookLMClient.from_storage` usado como context manager (sem `await` direto deprecado).
- `list_notebooks`: drift/erro upstream vira erro de domínio (não "lista vazia") — não apaga catálogo local.
- Storage por conta via `from_storage(storage_state_path)` — sem `NOTEBOOKLM_HOME` global.
- Polling trata `completed`/`failed`/`removed`/`not_found` persistente/timeout de forma terminal e previsível.
- `jobs`/`artifacts` com scoping por `account_id`.
- Autenticação Bearer _default-deny_ e CORS configurável por env.
- `AccountResponse` seguro (campos booleanos no lugar de paths).
- Erros da `notebooklm-py` mapeados para envelope HTTP seguro.

### Breaking Changes
- Rotas sensíveis exigem `Authorization: Bearer`, salvo `ALLOW_INSECURE_NO_AUTH=true`.
- `AccountResponse` remove `storage_state_path`, `chrome_profile_path` e `last_error`
  (textual); adiciona `enabled` e `has_chrome_profile` (mantém `has_storage_state`).
- `GET /jobs/{id}` e `GET /artifacts/{id}` cross-conta retornam **404** (indistinguível de inexistente).
- Erros upstream usam o envelope `ErrorResponse` (sem exceção crua).

### Security
- Removido vazamento de paths internos nas respostas de conta.
- Removido o `NOTEBOOKLM_HOME` global e o `global_env_lock` (estado global de auth).
- Removido retorno de exceção crua/stack trace nas respostas e na Web UI.
- Sanitização reforçada (cookies, `Authorization`/`Bearer`, `storage_state`, `chrome-profile`, paths, traceback).
- CORS fechado por padrão; `allow_credentials` nunca com `*`.

## [0.1.0]
- Versão inicial (MVP multi-account).
