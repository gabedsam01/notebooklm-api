# Smoke test manual (modo real)

> ⚠️ **Manual e sob sua confirmação.** Não roda no CI/suite. Exige cookies reais de
> uma **conta Google de teste**. **Nunca** use a conta pessoal principal e **nunca**
> publique cookies/tokens/`storage_state` em logs, prints ou issues.

## 1. Preparação

- [ ] Use uma **conta Google de teste** (descartável).
- [ ] Gere o `storage_state` de teste dessa conta e coloque-o no caminho da conta default
      (`data/auth/storage_state.json`) ou de uma conta criada (`data/accounts/acc_xxx/storage_state.json`).
- [ ] Rode local com auth:
      ```bash
      export API_AUTH_TOKEN="$(openssl rand -hex 32)"
      export NOTEBOOKLM_MODE=real
      python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
      ```
- [ ] Exporte o token no shell de teste (`H="Authorization: Bearer $API_AUTH_TOKEN"`).

## 2. Roteiro

- [ ] `GET /health` **sem** token → **200**.
- [ ] `GET /accounts` **sem** token → **401**.
- [ ] `GET /accounts` **com** token → **200** (sem paths internos no corpo).
- [ ] `POST /accounts/{id}/bootstrap` e `POST /accounts/{id}/verify` → status coerente (`warming`/`healthy`/`expired`/`challenge_required`).
- [ ] `POST /notebooks` (criar notebook) → **201**.
- [ ] `POST /sources/text` (adicionar fonte) → **200**.
- [ ] `POST /operations/audio-summary?async=true` (gerar artefato) → **202** (job_id).
- [ ] `GET /jobs/{job_id}` → acompanha `queued → running → waiting_remote → completed` (ou `failed`/`timed_out` previsível).
- [ ] `GET /artifacts/{job_id}` → **200** + binário (após `completed`).
- [ ] **Criar segunda conta** e repetir um job nela.
- [ ] **Isolamento:** com o header da **conta B**, `GET /jobs/{job_da_conta_A}` e `GET /artifacts/{...A}` → **404**.
- [ ] **Auth:** qualquer rota sensível **sem** token → **401**.
- [ ] **CORS** (se houver frontend): com `CORS_ALLOW_ORIGINS` configurado, preflight `OPTIONS` da origem permitida → **200** com `Access-Control-Allow-Origin`; origem não listada → sem `allow-origin`.

## 3. Critérios de sucesso

- Fluxo completo (notebook → fonte → gerar → poll → download) conclui em **modo real**.
- Isolamento por conta confirmado (404 cross-conta).
- Auth e CORS se comportam como configurado.
- **Nenhuma** resposta de erro contém cookie, `Bearer`, `storage_state`, `chrome-profile`, path interno ou traceback.

## 4. Limpeza dos dados de teste

- [ ] Pare o servidor.
- [ ] Remova/rotacione o `storage_state` de teste (e revogue a sessão no Google se necessário).
- [ ] Se for descartar tudo: `rm -rf data/` (apaga contas/jobs/artefatos locais de teste).

## 5. O que **não** publicar

- `storage_state`, cookies, `__Secure-*`, `SID`, qualquer `Bearer`/token real.
- Caminhos absolutos da máquina, dumps de `data/`, prints com headers `Authorization`.
