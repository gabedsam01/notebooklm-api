# Contributing

Obrigado por contribuir! Este projeto é uma API HTTP-first sobre a biblioteca
**não oficial** `notebooklm-py`. Leia também [SECURITY.md](SECURITY.md).

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
```

## Modo dev (sem token)

```bash
export ALLOW_INSECURE_NO_AUTH=true   # APENAS local; nunca em producao
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

## Rodar com autenticação

```bash
export API_AUTH_TOKEN="$(openssl rand -hex 32)"   # nunca comite o valor
curl -H "Authorization: Bearer $API_AUTH_TOKEN" http://localhost:8080/accounts
```

## Abrir issue / PR

- Descreva o problema com **passos para reproduzir** e resultado esperado vs. obtido.
- Inclua **logs sanitizados**.
- **Nunca** cole `storage_state`, cookies, `SID`/`__Secure-*`, tokens ou o header `Authorization`.

## Padrões de código

- **Testes obrigatórios** para mudanças de comportamento.
- **Sem sessão Google real** nos testes unitários — use **mocks/fakes** (`NOTEBOOKLM_MODE=mock`).
- Mantenha o **adapter** (`NotebookLMPyService`) isolando a `notebooklm-py` (não vaze tipos/exceções da lib para rotas).
- Não reintroduza `NOTEBOOKLM_HOME` global, `global_env_lock` nem cache de `NotebookLMClient`.
- Respeite o contrato público seguro: respostas não expõem paths internos, cookies nem exceções cruas.

## Checklist antes do PR

- [ ] `pytest -q` verde
- [ ] `python -m compileall app tests`
- [ ] Sem segredos (token/cookie/`storage_state`/`Authorization`)
- [ ] Sem paths internos em respostas públicas
- [ ] Docs atualizadas se o comportamento mudou

## Aviso

`notebooklm-py` é **não oficial** e usa endpoints internos do Google que podem
**mudar/quebrar** sem aviso (rate limit, challenge, 2FA, expiração de sessão).
