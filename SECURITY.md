# Segurança

## Versões suportadas

| Versão | Suporte |
|---|---|
| 0.2.x | ✅ correções de segurança |
| 0.1.x | ❌ não suportada (anterior à migração 0.2.0) |

## 1. Aviso (API não oficial)

- Este projeto usa a biblioteca **`notebooklm-py`**, que é **não oficial**.
- O **NotebookLM não oferece API pública oficial** para este uso.
- Os endpoints internos do Google **podem quebrar a qualquer momento**.
- Pode haver **rate limit, challenge, 2FA ou expiração de sessão** — a sessão **não é eterna**.

Use por sua conta e risco, preferencialmente com **conta de teste**.

## 2. Proteção da sessão (`storage_state`)

O `storage_state` contém **cookies de sessão do Google** (ex.: nomes como `SID`, `__Secure-1PSIDTS`). Quem tiver esse arquivo **pode se passar pela conta**.

- **Nunca** comite `storage_state` / `data/` (já estão no `.gitignore`).
- **Nunca** logue cookies, tokens ou o conteúdo do `storage_state`.
- **Nunca** exponha caminhos internos nem o conteúdo do `storage_state` via API (a 0.2.0 removeu `storage_state_path`/`chrome_profile_path` das respostas).
- Mantenha **permissões restritas** (o app grava o `storage_state` com `0o600`).
- Prefira uma **conta Google de teste**, não a conta pessoal principal.

## 3. API

- **`API_AUTH_TOKEN` é obrigatório em produção** (modelo _default-deny_: sem token e sem modo inseguro, rotas sensíveis retornam 401).
- **`ALLOW_INSECURE_NO_AUTH=true` é apenas para dev local** — nunca em produção.
- **CORS fechado por padrão**; libere apenas origens explícitas. `allow_credentials` nunca com `*`.
- Sirva **atrás de HTTPS** (proxy reverso); a app não termina TLS.
- Considere **rate limit no proxy** (não há rate limit embutido).
- `/health` é público; `/docs`/`/openapi.json` são públicos por decisão atual (expõem só o schema). Proteja-os no proxy se desejar.

**Checklist de deploy:** HTTPS no proxy · `API_AUTH_TOKEN` forte e secreto · `CORS_ALLOW_ORIGINS` restrito · `ALLOW_INSECURE_NO_AUTH=false` · **backup seguro de `data/`** antes de upgrades.

## 4. Logs e erros

- Há um **sanitizer best-effort** que remove cookies, `Authorization`/`Bearer`, `storage_state`, `chrome-profile`, paths internos e tracebacks das mensagens de erro internas/logs.
- O **envelope público de erro usa mensagens fixas por código** — o texto cru da exceção **nunca** vai para a resposta.
- Ainda assim, **não coloque segredos manualmente** em mensagens de erro, logs ou prints.
- O header `Authorization`/o token **nunca** são logados pela aplicação.

## 5. Web UI

- A Web UI fica **protegida pelo mesmo Bearer** das rotas sensíveis.
- Para uso em **browser**, utilize um **proxy seguro** que injete o header `Authorization`, ou o **modo dev inseguro apenas em desenvolvimento**. Não há login/sessão próprios.

## 6. Relato de vulnerabilidade

Encontrou um problema de segurança? **Não publique segredos.** Abra um aviso **privado** (GitHub Security Advisory, se disponível); se não houver, uma issue **sem** dados sensíveis, descrevendo o impacto e os passos. Aguarde resposta antes da divulgação pública.

**Nunca cole** (em issues, PRs, logs ou prints): `storage_state.json`, cookies (`SID`, `__Secure-1PSID`, `__Secure-1PSIDTS`), `API_AUTH_TOKEN`, o header `Authorization` / `Bearer ...` ou caminhos internos.
