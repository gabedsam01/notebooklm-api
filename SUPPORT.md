# Support

## Onde pedir ajuda

- **GitHub Issues** — bugs e dúvidas técnicas.
- **GitHub Discussions** — perguntas gerais, _if enabled_ no repositório.
- Vulnerabilidades de segurança: **siga o [SECURITY.md](SECURITY.md)** (não abra issue pública com segredo).

## O que **nunca** enviar

Em issues, discussions, logs ou prints, **nunca** inclua:

- `storage_state.json` ou seu conteúdo
- cookies do Google (`SID`, `__Secure-1PSID`, `__Secure-1PSIDTS`, etc.)
- `API_AUTH_TOKEN` ou qualquer token
- o header `Authorization` / `Bearer ...`
- caminhos internos sensíveis da sua máquina/servidor

## Como reportar um bug

Inclua:

1. **Versão** do projeto (ex.: `0.2.0`) e da `notebooklm-py`.
2. **Ambiente** (SO, versão do Python, `NOTEBOOKLM_MODE`).
3. **Comando/requisição** usada (sem segredos).
4. **Resultado esperado**.
5. **Resultado obtido** (com **logs sanitizados**).

Use o template de _Bug report_ ao abrir a issue.

## Como reportar uma vulnerabilidade

Siga o [SECURITY.md](SECURITY.md): prefira um **GitHub Security Advisory privado**;
não cole segredos. Não abra uma issue pública contendo dados sensíveis.
